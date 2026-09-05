"""Capture must preserve distinct events and survive delivery replay."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from atproto import models
from turbopuffer import InternalServerError, Turbopuffer

from bot.agent import _format_notifications_block
from bot.memory.encounters import append_encounters, notification_encounter
from bot.services.message_handler import MessageHandler
from bot.services.notification_poller import NotificationPoller
from bot.status import bot_status
from bot.tools._helpers import PhiDeps, notification_input

NOW = datetime(2026, 9, 5, 5, 0, tzinfo=UTC)
SUBJECT = "at://did:plc:65sucjiel52gefhcdcypynsr/app.bsky.feed.post/3muq4d7kyqi2v"
CID = "bafyreicaafen4qlk56o5yby5bykss5cwbf5lodep62dnw5alwft4mwrnhq"


def notification(actor="alice", handle="alice.test"):
    return models.AppBskyNotificationListNotifications.Notification.model_validate(
        {
            "uri": f"at://did:plc:{actor}/app.bsky.feed.like/one",
            "cid": CID,
            "author": {"did": f"did:plc:{actor}", "handle": handle},
            "reason": "like",
            "reasonSubject": SUBJECT,
            "indexedAt": "2026-09-05T04:59:01Z",
            "isRead": False,
            "record": {
                "$type": "app.bsky.feed.like",
                "createdAt": "2026-09-05T04:59:00Z",
                "subject": {"uri": SUBJECT, "cid": CID},
            },
        }
    )


def test_two_people_liking_one_post_remain_distinct():
    alice = notification_encounter(notification(), NOW)
    bob = notification_encounter(notification("bob", "bob.test"), NOW)
    assert alice["id"] != bob["id"]
    assert alice["subject_uri"] == bob["subject_uri"] == SUBJECT
    assert alice["event_uri"] != bob["event_uri"]
    assert alice["source_uris"] == [alice["event_uri"], SUBJECT]
    assert alice["source_created_at"] == "2026-09-05T04:59:00Z"
    assert alice["indexed_at"] == "2026-09-05T04:59:01.000000+00:00"
    assert alice["content"] == ""  # A like is not text authored by the liker.
    assert json.loads(alice["record_json"])["subject"]["uri"] == SUBJECT


def test_handle_change_and_redelivery_do_not_invent_a_new_event():
    before = notification_encounter(notification(), NOW)
    after = notification_encounter(
        notification(handle="renamed.test"), NOW + timedelta(days=1)
    )
    assert before["id"] == after["id"]
    assert before["actor_did"] == after["actor_did"]


def test_capture_requires_an_unambiguous_time():
    with pytest.raises(ValueError, match="timezone"):
        notification_encounter(notification(), NOW.replace(tzinfo=None))


def test_reply_body_and_thread_refs_survive_without_hydrating_the_post():
    raw = notification().model_dump(mode="json", by_alias=True)
    raw.update(
        uri="at://did:plc:alice/app.bsky.feed.post/one",
        reason="reply",
        record={
            "$type": "app.bsky.feed.post",
            "text": "nothing new to add",
            "createdAt": "2026-09-05T04:59:00Z",
            "reply": {
                "parent": {"uri": SUBJECT, "cid": CID},
                "root": {"uri": SUBJECT, "cid": CID},
            },
        },
    )
    event = notification_encounter(
        models.AppBskyNotificationListNotifications.Notification.model_validate(raw),
        NOW,
    )
    assert event["content"] == "nothing new to add"
    assert event["source_uris"] == [raw["uri"], SUBJECT]
    assert "decision" not in event


def test_changed_record_version_is_preserved_separately():
    original = notification()
    changed = original.model_copy(
        update={"cid": "bafyreidhfhtcdgfwthed75m377mkttnijg37mhigrh4tjqcn5ptjv2xp7e"}
    )
    assert (
        notification_encounter(original, NOW)["id"]
        != notification_encounter(changed, NOW)["id"]
    )


async def test_replay_preserves_first_capture_and_same_batch_duplicates_are_safe():
    stored = {}

    def serve(request):
        body = json.loads(request.content)
        assert body["upsert_condition"] == ["id", "Eq", None]
        rows = body["upsert_rows"]
        assert len({row["id"] for row in rows}) == len(rows)
        inserted = 0
        for row in rows:
            if row["id"] not in stored:
                stored[row["id"]] = row
                inserted += 1
        return httpx.Response(200, json={"rows_affected": inserted})

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        first = notification_encounter(notification(), NOW)
        replay = notification_encounter(
            notification(handle="renamed.test"), NOW + timedelta(days=1)
        )
        assert await append_encounters(client, "test-encounters", [first, first]) == 1
        assert await append_encounters(client, "test-encounters", [replay]) == 0
    saved = stored[first["id"]]
    assert saved["captured_at"] == NOW.isoformat()
    assert saved["actor_handle"] == "alice.test"


async def test_failed_capture_is_not_reported_as_success():
    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(503, json={"error": "unavailable"})
            )
        ),
    ) as client:
        with pytest.raises(InternalServerError):
            await append_encounters(
                client, "test-encounters", [notification_encounter(notification(), NOW)]
            )


async def test_silent_batch_is_captured_before_context_normalization(monkeypatch):
    stored = {}

    def serve(request):
        body = json.loads(request.content)
        for row in body["upsert_rows"]:
            stored.setdefault(row["id"], row)
        return httpx.Response(200, json={"rows_affected": len(stored)})

    async def decide(**kwargs):
        # The agent can choose no action; both encounters already exist.
        assert {row["actor_did"] for row in stored.values()} == {
            "did:plc:alice",
            "did:plc:bob",
        }

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        handler = MessageHandler.__new__(MessageHandler)
        handler._captured_versions = {}
        monkeypatch.setattr(
            handler,
            "client",
            SimpleNamespace(
                get_posts=AsyncMock(return_value=SimpleNamespace(posts=[]))
            ),
            raising=False,
        )
        run = AsyncMock(side_effect=decide)
        monkeypatch.setattr(
            handler,
            "agent",
            SimpleNamespace(
                memory=SimpleNamespace(client=client), process_notifications=run
            ),
            raising=False,
        )
        monkeypatch.setattr(
            handler, "_maybe_lookup_stranger", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            "bot.services.message_handler._limiter.hit", lambda *args: True
        )
        poller = NotificationPoller.__new__(NotificationPoller)
        monkeypatch.setattr(poller, "handler", handler, raising=False)
        seen = AsyncMock()
        monkeypatch.setattr(
            poller,
            "client",
            SimpleNamespace(
                mark_notifications_seen=seen,
                client=SimpleNamespace(get_current_time_iso=lambda: "t0"),
                get_notifications=AsyncMock(
                    return_value=SimpleNamespace(
                        notifications=[notification(), notification("bob", "bob.test")],
                        cursor=None,
                    )
                ),
            ),
            raising=False,
        )
        poller._semaphore = asyncio.Semaphore(1)
        poller._processed_uris = set()
        poller._first_poll = False
        poller._batch_task = None
        poller._background_tasks = set()
        monkeypatch.setattr(bot_status, "paused", False)
        await poller._check_notifications()
        assert poller._batch_task is not None
        await poller._batch_task
        run.assert_awaited_once()
        assert run.await_args is not None
        args = run.await_args.kwargs
        assert len(args["notification_events"]) == 2
        deps = PhiDeps(
            author_handle="",
            notifications_context=args["notifications_context"],
            notification_events=args["notification_events"],
        )
        block = _format_notifications_block(notification_input(deps))
        assert "@alice.test liked" in block and "@bob.test liked" in block
        assert notification().uri in block
        assert notification("bob", "bob.test").uri in block
        assert list(args["notifications_context"]) == [SUBJECT]
        seen.assert_awaited_once_with("t0")
    assert len(stored) == 2
    assert all(row["subject_uri"] == SUBJECT for row in stored.values())


@pytest.mark.parametrize("scenario", ["paused", "changed_version"])
async def test_received_versions_are_captured_independently_of_action_dispatch(
    monkeypatch, scenario
):
    poller = NotificationPoller.__new__(NotificationPoller)
    poller._first_poll = False
    poller._processed_uris = set()
    poller._background_tasks = set()
    poller._batch_task = None
    poller._semaphore = asyncio.Semaphore(1)
    first = notification()
    captured = []

    async def capture(batch):
        captured.extend(n.cid for n in batch)

    poller.client = SimpleNamespace(
        client=SimpleNamespace(get_current_time_iso=lambda: NOW.isoformat()),
        get_notifications=AsyncMock(),
        mark_notifications_seen=AsyncMock(),
    )
    poller.handler = SimpleNamespace(
        capture_notifications=AsyncMock(side_effect=capture),
        handle_batch=AsyncMock(),
    )
    monkeypatch.setattr(bot_status, "paused", scenario == "paused")
    delivered = [first]
    if scenario == "changed_version":
        delivered.append(first.model_copy(update={"cid": "changed-cid"}))
    for event in delivered:
        poller.client.get_notifications.return_value = SimpleNamespace(
            notifications=[event], cursor=None
        )
        await poller._check_notifications()
        if poller._batch_task is not None:
            await poller._batch_task
    assert captured == [event.cid for event in delivered]
    if scenario == "paused":
        poller.handler.handle_batch.assert_not_awaited()
        poller.client.mark_notifications_seen.assert_not_awaited()
    else:
        poller.handler.handle_batch.assert_awaited_once_with([first])


async def test_capture_cache_skips_only_successfully_stored_versions():
    attempts = []

    def serve(request):
        attempts.append(json.loads(request.content))
        if len(attempts) == 1:
            return httpx.Response(503, json={"error": "temporarily unavailable"})
        return httpx.Response(200, json={"rows_affected": 1})

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        handler = MessageHandler.__new__(MessageHandler)
        handler._captured_versions = {}
        handler.agent = SimpleNamespace(memory=SimpleNamespace(client=client))
        event = notification()
        with pytest.raises(InternalServerError):
            await handler.capture_notifications([event])
        assert not handler._captured_versions
        await handler.capture_notifications([event])
        await handler.capture_notifications([event])
        assert len(attempts) == 2
        changed = event.model_copy(update={"cid": CID + "x"})
        await handler.capture_notifications([changed])
        assert len(attempts) == 3
        assert len(handler._captured_versions) == 2
