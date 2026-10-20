"""Native post reads retain versioned context and attach actual image bytes."""

import json
from unittest.mock import AsyncMock

import pytest
from pydantic_ai import BinaryContent

from bot.core import post_reading as reading

URI = "at://did:plc:author/app.bsky.feed.post/post"


@pytest.fixture(autouse=True)
def no_network_replies(monkeypatch):
    monkeypatch.setattr(
        reading, "_replies_below", AsyncMock(return_value="@a.test [x] (1 reply): hi")
    )


PARENT = "at://did:plc:parent/app.bsky.feed.post/parent"


def parent_record():
    return {
        "uri": PARENT,
        "cid": "parent-version",
        "value": {
            "text": "see this",
            "embed": {
                "$type": "app.bsky.embed.images",
                "images": [
                    {
                        "image": {
                            "ref": {"$link": "image-cid"},
                            "mimeType": "image/jpeg",
                            "size": 5,
                        }
                    }
                ],
            },
        },
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://other.test/?next=https://bsky.app/profile/a.test/post/abc",
        "https://bsky.app.evil.test/profile/a.test/post/abc",
        "https://bsky.app/profile/a.test/post/abc/extra",
    ],
)
def test_only_actual_post_urls_route_natively(url):
    assert reading.post_uri_from_url(url) is None


def test_post_url_preserves_actor_and_ignores_query():
    assert (
        reading.post_uri_from_url("https://bsky.app/profile/a.test/post/abc?x=1")
        == "at://a.test/app.bsky.feed.post/abc"
    )


@pytest.mark.parametrize("changed", [False, True])
async def test_parent_version_and_image_attribution(monkeypatch, changed):
    parent = parent_record()
    post = {
        "uri": URI,
        "cid": "post-version",
        "value": {
            "text": "reply",
            "reply": {
                "parent": {"uri": PARENT, "cid": "parent-version"},
                "root": {"uri": PARENT, "cid": "parent-version"},
            },
        },
    }
    if changed:
        parent["cid"] = "changed-version"
    fetch = AsyncMock(side_effect=[post, parent])
    blob = AsyncMock(return_value=b"image")
    monkeypatch.setattr(reading, "fetch_record", fetch)
    monkeypatch.setattr(reading, "fetch_blob_bytes", blob)
    parts = await reading.read_post_url(
        "https://bsky.app/profile/a.test/post/post", URI
    )
    assert isinstance(parts[0], str)
    evidence = json.loads(parts[0])
    assert fetch.await_count == 2  # identical parent/root ref read only once
    assert "replies below it" in evidence["scope"]
    assert evidence["replies"] == "@a.test [x] (1 reply): hi"
    if changed:
        assert evidence["context"][0]["status"] == "version_changed"
        blob.assert_not_awaited()
        assert len(parts) == 1
    else:
        assert evidence["context"][0]["record"]["cid"] == "parent-version"
        blob.assert_awaited_once_with(
            "did:plc:parent", "image-cid", max_bytes=2_000_000
        )
        assert isinstance(parts[1], str)
        assert PARENT in parts[1]
        assert isinstance(parts[2], BinaryContent) and parts[2].data == b"image"


async def test_failed_image_remains_explicit(monkeypatch):
    monkeypatch.setattr(
        reading, "fetch_record", AsyncMock(return_value=parent_record())
    )
    monkeypatch.setattr(
        reading, "fetch_blob_bytes", AsyncMock(side_effect=ValueError("too large"))
    )
    parts = await reading.read_post_url(
        "https://bsky.app/profile/a.test/post/post", PARENT
    )
    assert isinstance(parts[0], str)
    assert json.loads(parts[0])["images"][0]["status"] == "unavailable"
    assert len(parts) == 1


async def test_image_budget_keeps_unread_images_visible(monkeypatch):
    record = parent_record()
    record["value"]["embed"]["images"] *= 2
    monkeypatch.setattr(reading, "MAX_IMAGES", 1)
    monkeypatch.setattr(reading, "fetch_record", AsyncMock(return_value=record))
    blob = AsyncMock(return_value=b"image")
    monkeypatch.setattr(reading, "fetch_blob_bytes", blob)
    parts = await reading.read_post_url("https://bsky.app", PARENT)
    assert isinstance(parts[0], str)
    evidence = json.loads(parts[0])
    assert [image["status"] for image in evidence["images"]] == [
        "attached",
        "not_loaded",
    ]
    assert blob.await_count == 1


async def test_replies_below_render_as_a_nested_thread(monkeypatch):
    """2026-10-20: read_web_page is phi's reader for any bsky link, and it
    left every reply out, so a conversation read as a single post."""
    thread = {
        "post": {
            "uri": URI,
            "author": {"handle": "a.test"},
            "record": {"text": "question"},
            "replyCount": 1,
        },
        "replies": [
            {
                "post": {
                    "uri": PARENT,
                    "author": {"handle": "b.test"},
                    "record": {"text": "answer"},
                    "replyCount": 3,
                },
                "replies": [],
            }
        ],
    }

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"thread": thread}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url, params):
            assert params["uri"] == URI
            return Response()

    monkeypatch.undo()
    monkeypatch.setattr(reading.httpx, "AsyncClient", Client)
    assert await reading._replies_below(URI) == (
        f"@a.test [{URI}] (1 reply): question\n"
        f"  @b.test [{PARENT}] (3 replies): answer\n"
        f"    … 3 more replies below, read-thread from [{PARENT}]"
    )
