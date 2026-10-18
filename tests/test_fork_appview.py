"""Notifications from Bluesky forks reach the batch and replies land back there.

2026-10-18: the operator mentioned phi in a Delvetown post. Delvetown is a
Bluesky fork with its own `town.delve.*` namespace and AppView, so the
mention never appeared in Bluesky's notification list and phi never saw it.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from atproto import models

from bot.agent import _format_notifications_block
from bot.core import fork_appview
from bot.core.fork_appview import ForkAppView, app_for_uri, as_app, as_bluesky
from bot.services.message_handler import MessageHandler
from bot.services.notification_poller import NotificationPoller
from bot.tools import posting
from bot.tools._helpers import PhiDeps

NATE = "did:plc:xbtmt2zjwlrfegqvch7fboei"
PHI = "did:plc:65sucjiel52gefhcdcypynsr"
CID = "bafyreib2rxk3rh6kzwq3ixrvvq5ovgrrbmamw5hsxetqfpq3vugcqd3ypm"
DELVE_POST = f"at://{NATE}/town.delve.feed.post/3my66hygpr22e"
BSKY_POST = f"at://{NATE}/app.bsky.feed.post/3my66hygpr22e"
DELVE = app_for_uri(DELVE_POST)


def delve_mention(is_read: bool = False) -> dict:
    return {
        "uri": DELVE_POST,
        "cid": CID,
        "author": {
            "$type": "town.delve.actor.defs#profileView",
            "did": NATE,
            "handle": "zzstoatzz.io",
        },
        "reason": "mention",
        "record": {
            "$type": "town.delve.feed.post",
            "text": "@phi.zzstoatzz.io we should tell some friends on here",
            "createdAt": "2026-10-18T17:55:00.000Z",
            "facets": [
                {
                    "index": {"byteStart": 0, "byteEnd": 17},
                    "features": [
                        {"$type": "town.delve.richtext.facet#mention", "did": PHI}
                    ],
                }
            ],
        },
        "isRead": is_read,
        "indexedAt": "2026-10-18T17:55:01.000Z",
    }


def test_uris_name_their_app():
    assert DELVE is not None and DELVE.name == "delve.town"
    assert app_for_uri(f"at://{NATE}/town.delve.feed.like/x") == DELVE
    assert app_for_uri(f"at://{NATE}/town.delve.graph.follow/x") == DELVE
    assert app_for_uri(BSKY_POST) is None


def test_retyping_touches_types_not_text():
    assert DELVE is not None
    view = {"$type": "town.delve.feed.defs#postView", "text": '"town.delve.x'}
    bsky = as_bluesky(view, DELVE)
    assert bsky == {"$type": "app.bsky.feed.defs#postView", "text": '"town.delve.x'}
    assert as_app(bsky, DELVE) == view


async def test_delve_notifications_parse_as_bluesky_models():
    assert DELVE is not None
    view = ForkAppView(DELVE, Mock(authenticate=AsyncMock()))
    with patch.object(
        view, "_call", return_value={"notifications": [delve_mention()]}
    ) as call:
        page = await view.get_notifications(limit=100, priority=False)
    assert call.call_args.args[:2] == ("query", "notification.listNotifications")
    (n,) = page.notifications
    assert n.uri == DELVE_POST and n.author.handle == "zzstoatzz.io"
    assert isinstance(n.record, models.AppBskyFeedPost.Record)
    assert n.record.text.startswith("@phi.zzstoatzz.io") and not n.is_read


def _poller(views: list) -> NotificationPoller:
    client = Mock()
    client.mark_notifications_seen = AsyncMock()
    client.client.get_current_time_iso.return_value = "2026-10-18T18:00:00Z"
    client.get_notifications = AsyncMock(
        return_value=SimpleNamespace(notifications=[], cursor=None)
    )
    poller = NotificationPoller.__new__(NotificationPoller)
    poller.client = client
    poller.app_views = views
    poller._app_poll_failing = set()
    poller._first_poll = False
    poller._semaphore = asyncio.Semaphore(1)
    poller._batch_task = None
    poller._processed_uris = set()
    poller._background_tasks = set()
    poller.handler = Mock(capture_notifications=AsyncMock(), handle_batch=AsyncMock())
    return poller


async def test_delve_mention_joins_the_batch_and_is_marked_seen_there(monkeypatch):
    from bot.status import bot_status

    monkeypatch.setattr(bot_status, "paused", False)
    assert DELVE is not None
    view = ForkAppView(DELVE, Mock(authenticate=AsyncMock()))
    page = {"notifications": [delve_mention()]}
    sent: dict[str, dict] = {}

    def call(kind, method, arguments):
        sent[method] = arguments
        return page if method == "notification.listNotifications" else {}

    monkeypatch.setattr(view, "_call", call)
    poller = _poller([view])
    handle_batch = poller.handler.handle_batch = AsyncMock()
    capture = poller.handler.capture_notifications = AsyncMock()
    await poller._check_notifications()
    assert poller._batch_task is not None
    await poller._batch_task

    assert handle_batch.await_args is not None
    (batch,) = handle_batch.await_args.args
    assert [n.uri for n in batch] == [DELVE_POST]
    capture.assert_awaited()
    assert sent["notification.updateSeen"] == {"seenAt": "2026-10-18T18:00:00Z"}


async def test_unreadable_app_costs_nothing_but_its_own_events(monkeypatch):
    assert DELVE is not None
    view = ForkAppView(DELVE, Mock(authenticate=AsyncMock()))
    monkeypatch.setattr(view, "_call", Mock(side_effect=RuntimeError("not a member")))
    poller = _poller([view])
    assert await poller._app_notifications(view) == []
    assert await poller._app_notifications(view) == []
    assert poller._app_poll_failing == {"delve.town"}


async def test_delve_entry_is_hydrated_by_delve_and_labeled():
    assert DELVE is not None
    handler = MessageHandler.__new__(MessageHandler)
    handler.client = Mock()
    handler.client.get_posts = AsyncMock(side_effect=AssertionError("bluesky"))
    n = SimpleNamespace(uri=DELVE_POST, reason="mention")
    view = handler._view_for(n)
    assert isinstance(view, ForkAppView) and view.app == DELVE
    assert handler._view_for(SimpleNamespace(uri=BSKY_POST)) is handler.client


def test_block_says_where_the_thread_lives_and_where_replies_go():
    block = _format_notifications_block(
        {
            DELVE_POST: {
                "uri": DELVE_POST,
                "reason": "mention",
                "author_handle": "zzstoatzz.io",
                "post_text": "we should tell some friends on here",
                "root_uri": DELVE_POST,
                "app": "delve.town",
            },
            f"at://{PHI}/town.delve.feed.post/mine": {
                "uri": f"at://{PHI}/town.delve.feed.post/mine",
                "reason": "like",
                "author_handle": "friend.test",
                "post_text": "my delve post",
                "app": "delve.town",
            },
            BSKY_POST: {
                "uri": BSKY_POST,
                "reason": "mention",
                "author_handle": "zzstoatzz.io",
                "post_text": "over on bluesky",
                "root_uri": BSKY_POST,
            },
        }
    )
    lines = block.splitlines()
    frame = lines.index(
        next(line for line in lines if line.startswith("on delve.town"))
    )
    assert "publishes your reply on delve.town" in lines[frame]
    assert lines[frame + 1].startswith(f"@zzstoatzz.io [{DELVE_POST}]")
    assert "@friend.test liked your post on delve.town" in block
    bsky_line = lines.index(f"@zzstoatzz.io [{BSKY_POST}]: over on bluesky")
    assert not lines[bsky_line - 1].startswith("on ")


def _post_tool() -> dict:
    captured = {}
    posting.register(
        SimpleNamespace(tool=lambda fn: captured.setdefault(fn.__name__, fn))
    )
    return captured


async def test_reply_to_a_delve_post_is_written_on_delve():
    tools = _post_tool()
    notifs = {
        DELVE_POST: {
            "uri": DELVE_POST,
            "cid": CID,
            "reason": "mention",
            "author_handle": "zzstoatzz.io",
            "post_text": "we should tell some friends on here",
            "root_uri": DELVE_POST,
            "root_cid": CID,
            "app": "delve.town",
        }
    }
    ctx = SimpleNamespace(
        deps=PhiDeps(author_handle="zzstoatzz.io", notifications_context=notifs)
    )
    written = SimpleNamespace(uri=f"at://{PHI}/town.delve.feed.post/reply", cid=CID)
    with (
        patch.object(
            posting, "get_override", AsyncMock(return_value={"active": False})
        ),
        patch.object(
            posting, "_policy_gate", AsyncMock(return_value=(None, ""))
        ) as gate,
        patch.object(posting, "_build_allowed_handles", AsyncMock(return_value=set())),
        patch.object(posting, "reply_coverage", AsyncMock()) as coverage,
        patch.object(posting.bot_client, "create_post", AsyncMock()) as bsky_post,
        patch.object(
            posting, "create_app_reply", AsyncMock(return_value=written)
        ) as app_reply,
    ):
        result = await tools["post"](ctx, "yes! who first?", in_reply_to=DELVE_POST)

    bsky_post.assert_not_awaited()
    coverage.assert_not_awaited()
    assert app_reply.await_args is not None
    assert app_reply.await_args.args[0] == DELVE
    assert app_reply.await_args.kwargs["parent"] == {"uri": DELVE_POST, "cid": CID}
    assert app_reply.await_args.kwargs["root"] == {"uri": DELVE_POST, "cid": CID}
    assert gate.await_args is not None
    assert gate.await_args.args[0].startswith(f"reply on delve.town to {DELVE_POST}")
    assert "publishes on delve.town" in gate.await_args.args[1]
    assert result.startswith(f"published on delve.town: {written.uri}")


async def test_delve_replies_are_one_text_post():
    tools = _post_tool()
    ctx = SimpleNamespace(deps=PhiDeps(author_handle="zzstoatzz.io"))
    with (
        patch.object(
            posting, "get_override", AsyncMock(return_value={"active": False})
        ),
        patch.object(posting, "create_app_reply", AsyncMock()) as app_reply,
    ):
        quoted = await tools["post"](
            ctx, "look", in_reply_to=DELVE_POST, quote=BSKY_POST
        )
        long = await tools["post"](ctx, "word " * 80, in_reply_to=DELVE_POST)
    assert quoted.startswith("refused: replies on delve.town are text only")
    assert long.startswith("refused: a reply on delve.town is one post")
    app_reply.assert_not_awaited()


async def test_app_reply_record_lives_in_the_app_namespace():
    assert DELVE is not None
    create = Mock(return_value=SimpleNamespace(uri="at://phi/x/y", cid=CID))
    client = SimpleNamespace(
        me=SimpleNamespace(did=PHI),
        com=SimpleNamespace(
            atproto=SimpleNamespace(repo=SimpleNamespace(create_record=create))
        ),
    )
    facets = [
        {
            "index": {"byteStart": 0, "byteEnd": 13},
            "features": [{"$type": "app.bsky.richtext.facet#mention", "did": NATE}],
        }
    ]
    with (
        patch.object(fork_appview.bot_client, "authenticate", AsyncMock()),
        patch.object(fork_appview.bot_client, "client", client),
        patch.object(fork_appview, "create_facets", return_value=facets),
    ):
        await fork_appview.create_app_reply(
            DELVE,
            "@zzstoatzz.io yes",
            parent={"uri": DELVE_POST, "cid": CID},
            root={"uri": DELVE_POST, "cid": CID},
            allowed_handles={"zzstoatzz.io"},
        )
    data = create.call_args.kwargs["data"]
    assert data["repo"] == PHI and data["collection"] == "town.delve.feed.post"
    record = data["record"]
    assert record["$type"] == "town.delve.feed.post"
    assert record["reply"]["parent"]["uri"] == DELVE_POST
    feature = record["facets"][0]["features"][0]
    assert feature == {"$type": "town.delve.richtext.facet#mention", "did": NATE}
