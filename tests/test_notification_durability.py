"""Mark-seen timing: a batch the process dies holding must stay unread.

2026-08-07: a mention landed mid-deploy; the poller marked it seen at
dispatch, the machine restarted before the run replied, and phi never saw
the thread. Seen now happens after the handler finishes — died-holding
batches are re-fetched unread by the next process.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot.services.notification_poller import NotificationPoller
from bot.status import bot_status


def _poller():
    client = Mock()
    client.mark_notifications_seen = AsyncMock()
    poller = NotificationPoller.__new__(NotificationPoller)
    poller.client = client
    poller._semaphore = asyncio.Semaphore(1)
    poller._batch_task = None
    poller._processed_uris = set()
    poller._background_tasks = set()
    poller.handler = Mock()
    poller.handler.capture_notifications = AsyncMock()
    return poller


async def test_unfetched_backlog_must_not_be_acknowledged(monkeypatch):
    """Characterize the recovery gap before shipping the capture prototype."""
    poller = _poller()
    poller._first_poll = False
    monkeypatch.setattr(bot_status, "paused", False)
    events = [
        SimpleNamespace(
            uri=f"at://did:plc:alice/app.bsky.feed.like/{i}",
            cid=f"cid-{i}",
            author=SimpleNamespace(handle="alice.test"),
            reason="like",
            reason_subject="at://did:plc:phi/app.bsky.feed.post/one",
            indexed_at="2026-09-05T00:00:00Z",
            is_read=False,
        )
        for i in range(175)
    ]
    captured = set()

    async def fetch(limit=50, cursor=None, priority=None):
        offset = int(cursor or 0)
        end = offset + limit
        return SimpleNamespace(
            notifications=events[offset:end],
            cursor=str(end) if end < len(events) else None,
        )

    async def capture(batch):
        captured.update(n.uri for n in batch)

    async def seen(check_time):
        for event in events:
            if event.indexed_at <= check_time:
                event.is_read = True

    poller.client.client.get_current_time_iso.return_value = "2026-09-05T00:01:00Z"
    poller.client.get_notifications = AsyncMock(side_effect=fetch)
    poller.client.mark_notifications_seen.side_effect = seen
    poller.handler.capture_notifications.side_effect = capture
    poller.handler.handle_batch = AsyncMock()
    await poller._check_notifications()
    await poller._batch_task

    acknowledged = {n.uri for n in events if n.is_read}
    assert len(captured) == 175
    assert acknowledged == captured
    assert poller.client.get_notifications.await_count == 2


async def test_seen_marked_only_after_handler_completes():
    poller = _poller()
    order: list[str] = []

    async def handle_batch(batch):
        order.append("handled")

    async def seen(check_time):
        order.append("seen")

    poller.handler.handle_batch = handle_batch
    poller.client.mark_notifications_seen.side_effect = seen
    await poller._handle_batch_with_semaphore(["n"], "t0")
    assert order == ["handled", "seen"]


async def test_capture_failure_prevents_claiming_running_or_marking_seen(monkeypatch):
    poller = _poller()
    poller._first_poll = False
    monkeypatch.setattr(bot_status, "paused", False)
    event = SimpleNamespace(
        uri="at://alice/like/one",
        cid="cid",
        reason="like",
        is_read=False,
        author=SimpleNamespace(handle="alice.test"),
    )
    poller.client.get_notifications = AsyncMock(
        return_value=SimpleNamespace(notifications=[event], cursor=None)
    )
    poller.client.client.get_current_time_iso.side_effect = ["t0", "t1"]
    poller.handler.capture_notifications.side_effect = [
        RuntimeError("store down"),
        None,
    ]
    poller.handler.handle_batch = AsyncMock()
    with pytest.raises(RuntimeError, match="store down"):
        await poller._check_notifications()
    assert poller._batch_task is None
    assert event.uri not in poller._processed_uris
    poller.handler.handle_batch.assert_not_awaited()
    poller.client.mark_notifications_seen.assert_not_awaited()

    await poller._check_notifications()
    assert poller._batch_task is not None
    await poller._batch_task
    poller.handler.handle_batch.assert_awaited_once_with([event])
    poller.client.mark_notifications_seen.assert_awaited_once_with("t1")


async def test_crash_mid_batch_leaves_notifications_unread():
    """Process death (task cancellation) before the handler finishes must
    not mark seen — this is the regression: at dispatch-time marking, the
    2026-08-07 mention was consumed by a deploy restart."""
    poller = _poller()
    started = asyncio.Event()

    async def hang(batch):
        started.set()
        await asyncio.sleep(60)

    poller.handler.handle_batch = hang
    task = asyncio.create_task(poller._handle_batch_with_semaphore(["n"], "t0"))
    await started.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    poller.client.mark_notifications_seen.assert_not_awaited()


async def test_handler_failure_still_marks_seen():
    """A poison batch must not be retried every 10s forever."""
    poller = _poller()

    async def boom(batch):
        raise RuntimeError("model down")

    poller.handler.handle_batch = boom
    await poller._handle_batch_with_semaphore(["n"], "t0")
    poller.client.mark_notifications_seen.assert_awaited_once_with("t0")


async def test_follow_ups_wait_for_the_in_flight_run_and_batch_together():
    """2026-08-21: three devlog posts ~25s apart became three concurrent
    one-item runs and seven replies. A second dispatch while one run is in
    flight must be declined and leave its items unclaimed, so the next poll
    after the run finishes batches everything that arrived."""
    poller = _poller()
    release = asyncio.Event()
    handled: list[list] = []

    async def handle_batch(batch):
        handled.append(list(batch))
        await release.wait()

    poller.handler.handle_batch = handle_batch
    first = Mock(uri="at://x/1")
    second = Mock(uri="at://x/2")
    third = Mock(uri="at://x/3")

    assert poller._dispatch_batch([first], "t0") is True
    await asyncio.sleep(0)
    assert poller._dispatch_batch([second], "t1") is False
    assert second.uri not in poller._processed_uris

    release.set()
    await poller._batch_task
    assert poller._dispatch_batch([second, third], "t2") is True
    await poller._batch_task
    assert handled == [[first], [second, third]]


async def test_partial_scan_failure_never_dispatches_or_acknowledges(monkeypatch):
    poller = _poller()
    poller._first_poll = False
    monkeypatch.setattr(bot_status, "paused", False)
    poller.client.get_notifications = AsyncMock(
        side_effect=[
            SimpleNamespace(
                notifications=[
                    SimpleNamespace(
                        uri="event", cid="cid", reason="mention", is_read=False
                    )
                ],
                cursor="remaining",
            ),
            RuntimeError("page fetch failed"),
        ]
    )
    try:
        await poller._check_notifications()
    except RuntimeError as exc:
        assert str(exc) == "page fetch failed"
    else:
        raise AssertionError("An incomplete scan must propagate its failure")
    assert poller._batch_task is None
    assert not poller._processed_uris
    poller.handler.capture_notifications.assert_awaited_once()
    poller.client.mark_notifications_seen.assert_not_awaited()
