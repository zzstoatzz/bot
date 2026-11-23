"""Event participants must not replace post authors or collapse authorization."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from atproto import models
from pydantic_ai import RunContext

from bot.agent import PhiAgent, _format_notifications_block
from bot.config import settings
from bot.services.message_handler import MessageHandler
from bot.tools._helpers import PhiDeps, _is_owner, notification_input
from bot.tools.posting import _resolve_post_ref

TARGET = "at://did:plc:phi/app.bsky.feed.post/one"


def test_two_actors_on_one_target_remain_a_mixed_batch():
    stranger = {"uri": TARGET, "author_handle": "stranger.test", "reason": "like"}
    owner = {"uri": TARGET, "author_handle": settings.owner_handle, "reason": "like"}
    deps = PhiDeps(
        author_handle="",
        notifications_context={TARGET: owner},
        notification_events=[stranger, owner],
    )
    assert not _is_owner(Mock(spec=RunContext, deps=deps))
    assert len(notification_input(deps)) == 2


async def test_reply_reference_keeps_post_author_separate_from_liker():
    entry = {
        "uri": TARGET,
        "cid": "post-cid",
        "root_uri": TARGET,
        "root_cid": "root-cid",
        "author_handle": "liker.test",
        "post_author_handle": settings.bluesky_handle,
        "post_text": "Phi's post",
    }
    ref = await _resolve_post_ref(TARGET, {TARGET: entry})
    assert ref == (
        "post-cid",
        TARGET,
        "root-cid",
        settings.bluesky_handle,
        "Phi's post",
    )
    # An unavailable target author must not become the actor who liked it.
    entry["post_author_handle"] = ""
    ref = await _resolve_post_ref(TARGET, {TARGET: entry})
    assert ref is not None
    assert ref[3] == ""


@pytest.mark.parametrize("failure", [False, True])
async def test_unavailable_post_reaches_real_agent_entry_without_verified_target(
    monkeypatch, failure
):
    notification = (
        models.AppBskyNotificationListNotifications.Notification.model_validate(
            {
                "uri": TARGET,
                "cid": "bafyreicaafen4qlk56o5yby5bykss5cwbf5lodep62dnw5alwft4mwrnhq",
                "author": {"did": "did:plc:alice", "handle": "alice.test"},
                "reason": "reply",
                "indexedAt": "2026-09-05T04:59:01Z",
                "isRead": False,
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": "I already answered this yesterday.",
                    "createdAt": "2026-09-05T04:59:00Z",
                },
            }
        )
    )
    handler = MessageHandler.__new__(MessageHandler)
    handler.client = Mock(
        get_posts=AsyncMock(
            side_effect=RuntimeError("network failed") if failure else None,
            return_value=SimpleNamespace(posts=[]),
        )
    )
    handler.agent = PhiAgent.__new__(PhiAgent)
    handler.agent.memory = None
    run = AsyncMock(return_value="no action")
    monkeypatch.setattr(handler.agent, "_run_agent", run)
    monkeypatch.setattr(handler, "_maybe_lookup_stranger", AsyncMock(return_value=None))
    monkeypatch.setattr("bot.services.message_handler._limiter.hit", lambda *args: True)
    await handler.handle_batch([notification])
    run.assert_awaited_once()
    assert run.await_args is not None
    deps = run.await_args.kwargs["deps"]
    assert deps.notifications_context == {}
    block = _format_notifications_block(notification_input(deps))
    assert isinstance(notification.record, models.AppBskyFeedPost.Record)
    assert notification.record.text in block
    assert notification.cid in block
    assert TARGET in block
    assert ("lookup failed" if failure else "not returned by lookup") in block
    assert "not a verified current reply target" in block
    fetch_record = AsyncMock(side_effect=RuntimeError("still unavailable"))
    monkeypatch.setattr("bot.tools.posting.fetch_record", fetch_record)
    assert await _resolve_post_ref(TARGET, deps.notifications_context) is None
    fetch_record.assert_awaited_once()


async def test_out_of_batch_post_is_verified_on_its_authors_pds(monkeypatch):
    """Phi's PDS answers getRecord only for repos it hosts, so a like or reply
    target must be read from the PDS in the author's DID document."""
    did = "did:plc:alice"
    uri = f"at://{did}/app.bsky.feed.post/3kabc"
    root = {"uri": f"at://{did}/app.bsky.feed.post/3kroot", "cid": "root-cid"}
    seen: list[httpx.URL] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(
            200,
            json={
                "uri": uri,
                "cid": "post-cid",
                "value": {"text": "hello", "reply": {"root": root, "parent": root}},
            },
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "bot.core.media.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw),
    )
    monkeypatch.setattr(
        "bot.core.media.identity.pds_for",
        AsyncMock(return_value="https://pds.alice.test"),
    )
    own_pds = Mock()
    monkeypatch.setattr("bot.tools.posting.bot_client", own_pds)

    assert await _resolve_post_ref(uri, {}) == (
        "post-cid",
        root["uri"],
        "root-cid",
        "",
        "hello",
    )
    assert [(u.host, u.path, dict(u.params)) for u in seen] == [
        (
            "pds.alice.test",
            "/xrpc/com.atproto.repo.getRecord",
            {"repo": did, "collection": "app.bsky.feed.post", "rkey": "3kabc"},
        )
    ]
    own_pds.client.com.atproto.repo.get_record.assert_not_called()
