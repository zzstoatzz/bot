"""Image posts use the same bytes for policy review and the public embed."""

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from atproto_client import models
from atproto_client.models.blob_ref import BlobRef
from PIL import Image
from pydantic_ai import BinaryContent

from bot.core import policy, post_images
from bot.core.atproto_client import BotClient
from bot.core.post_images import PostImage, prepare_images
from bot.tools import posting
from bot.tools._helpers import PhiDeps

CID = "bafkreigh2akiscaildc5m7xxxrrvqcrniiy3uosso7i5rlqrnm7ubv24ya"
DID = "did:plc:65sucjiel52gefhcdcypynsr"
URI = f"at://{DID}/app.bsky.feed.post/parent"


def picture():
    output = io.BytesIO()
    Image.new("RGB", (32, 24), "orange").save(output, format="PNG")
    data = output.getvalue()
    return data, PostImage(
        blob=BlobRef.model_validate(
            {
                "$type": "blob",
                "ref": {"$link": CID},
                "mimeType": "image/png",
                "size": len(data),
            }
        ),
        alt="A caption: this is fine",
    )


async def test_prepare_images_keeps_pixels_alt_and_blob_together():
    data, image = picture()
    with patch.object(
        post_images, "fetch_blob_bytes", AsyncMock(return_value=data)
    ) as fetch:
        embed, pixels, description = await prepare_images(DID, [image])
    fetch.assert_awaited_once_with(DID, CID, max_bytes=1_000_000)
    assert pixels[0].data == data
    assert pixels[0].media_type == "image/png"
    assert embed.images[0].image == image.blob
    assert embed.images[0].alt == image.alt
    assert embed.images[0].aspect_ratio.width == 32
    assert embed.images[0].aspect_ratio.height == 24
    assert image.alt in description and CID in description


@pytest.mark.parametrize("defect", ["size", "mime", "invalid"])
async def test_invalid_images_are_rejected_before_review(defect):
    data, image = picture()
    if defect == "size":
        image.blob.size += 1
    if defect == "mime":
        image.blob.mime_type = "image/jpeg"
    if defect == "invalid":
        data = b"x" * image.blob.size
    with patch.object(post_images, "fetch_blob_bytes", AsyncMock(return_value=data)):
        with pytest.raises((ValueError, OSError)):
            await prepare_images(DID, [image])


async def test_judge_receives_actual_image_bytes_and_caption():
    data, _ = picture()
    judge = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(output={"verdict": "allow"}))
    )
    with patch.object(policy, "_get_judge", return_value=judge):
        await policy.check_action(
            "caption text",
            "invited",
            images=[BinaryContent(data=data, media_type="image/png")],
        )
    payload = judge.run.await_args.args[0]
    assert "caption text" in payload[0]
    assert payload[1].data == data


@pytest.mark.parametrize("reply", [False, True])
@pytest.mark.parametrize("blocked", [False, True])
async def test_post_image_uses_policy_and_preserves_reply_refs(reply, blocked):
    data, image = picture()
    captured = {}
    posting.register(
        SimpleNamespace(tool=lambda fn: captured.setdefault(fn.__name__, fn))
    )
    ctx = SimpleNamespace(deps=PhiDeps(author_handle="friend.bsky.social"))
    with (
        patch.object(
            posting, "get_override", AsyncMock(return_value={"active": False})
        ),
        patch.object(posting.bot_client, "authenticate", AsyncMock()),
        patch.object(
            posting.bot_client, "client", SimpleNamespace(me=SimpleNamespace(did=DID))
        ),
        patch.object(post_images, "fetch_blob_bytes", AsyncMock(return_value=data)),
        patch.object(
            posting,
            "_resolve_post_ref",
            AsyncMock(return_value=(CID, URI, CID, "friend.bsky.social", "hello")),
        ),
        patch.object(posting, "_build_allowed_handles", AsyncMock(return_value=set())),
        patch.object(posting, "coverage_note", AsyncMock(return_value="")),
        patch.object(posting, "_recent_own_posts", return_value=""),
        patch.object(
            posting,
            "check_action",
            AsyncMock(
                return_value={
                    "verdict": "block" if blocked else "allow",
                    "policy": "uninvited-reply",
                    "reason": "test",
                }
            ),
        ) as judge,
        patch.object(
            posting.bot_client,
            "create_post",
            AsyncMock(return_value=SimpleNamespace(uri=URI)),
        ) as create,
    ):
        result = await captured["post"](
            ctx, "caption", in_reply_to=URI if reply else "", images=[image]
        )
    assert judge.await_args is not None
    assert judge.await_args.kwargs["images"][0].data == data
    assert image.alt in judge.await_args.kwargs["action"]
    if blocked:
        create.assert_not_called()
        assert "blocked" in result
    else:
        assert create.await_args is not None
        assert create.await_args.kwargs["embed"].images[0].image == image.blob
        if reply:
            ref = create.await_args.kwargs["reply_to"]
            assert ref.parent.uri == URI and ref.parent.cid == CID
            assert ref.root.uri == URI


@pytest.mark.parametrize("reply", [False, True])
async def test_split_thread_attaches_image_only_to_first_post(reply):
    _, image = picture()
    embed = models.AppBskyEmbedImages.Main(
        images=[models.AppBskyEmbedImages.Image(image=image.blob, alt=image.alt)]
    )
    client = BotClient.__new__(BotClient)
    client.authenticate = AsyncMock()
    client.client = SimpleNamespace(
        send_post=Mock(
            side_effect=[
                SimpleNamespace(uri=f"at://{DID}/app.bsky.feed.post/{i}", cid=CID)
                for i in range(10)
            ]
        )
    )
    parent = models.ComAtprotoRepoStrongRef.Main(uri=URI, cid=CID)
    ref = models.AppBskyFeedPost.ReplyRef(parent=parent, root=parent) if reply else None
    with (
        patch("bot.core.atproto_client.create_facets", return_value=[]),
        patch("bot.core.atproto_client.record_local_write"),
    ):
        await client.create_post("word " * 150, reply_to=ref, embed=embed)
    calls = client.client.send_post.call_args_list
    assert len(calls) > 1
    assert calls[0].kwargs["embed"] == embed
    assert calls[0].kwargs["reply_to"] == ref
    assert all("embed" not in c.kwargs for c in calls[1:])
    expected_root = URI if reply else f"at://{DID}/app.bsky.feed.post/0"
    assert all(c.kwargs["reply_to"].root.uri == expected_root for c in calls[1:])


async def test_unreferenced_generated_blob_uses_durable_bytes(monkeypatch, tmp_path):
    from bot.core import generated_images

    data, image = picture()
    monkeypatch.setattr(generated_images, "cache_directory", lambda: tmp_path)
    generated_images.remember_image(CID, data)
    with patch.object(
        post_images,
        "fetch_blob_bytes",
        AsyncMock(side_effect=RuntimeError("PDS cannot serve unreferenced blobs")),
    ) as fetch:
        embed, pixels, _ = await prepare_images(DID, [image])
    fetch.assert_not_called()
    assert pixels[0].data == data
    assert embed.images[0].image == image.blob
    # Reading it again uses disk, without a generation response in memory.
    assert generated_images.recalled_image(CID) == data


def test_generated_image_cache_is_bounded(monkeypatch, tmp_path):
    from bot.core import generated_images

    monkeypatch.setattr(generated_images, "cache_directory", lambda: tmp_path)
    monkeypatch.setattr(generated_images, "MAX_FILES", 2)
    for cid in ["baaa", "baab", "baac"]:
        generated_images.remember_image(cid, b"bytes")
    assert len(list(tmp_path.glob("*.blob"))) == 2
    assert generated_images.recalled_image("baac") == b"bytes"
    with pytest.raises(ValueError):
        generated_images.recalled_image("../outside")
