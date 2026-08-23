"""/health must fail when phi is wedged.

The poll loop swallows exceptions at every site, so a dead loop still
reports ``polling_active: true``. The heartbeat is the one signal it
cannot fake: it only advances after an iteration completes its
notification check. Fly restarts the machine on a failing check, so a
false 200 is a wedge nobody notices and a false 503 is a restart loop.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

from starlette.testclient import TestClient

import bot.main as m
from bot.config import settings
from bot.services.notification_poller import NotificationPoller
from bot.status import BotStatus, bot_status

client = TestClient(m.app)


def _reset():
    bot_status.polling_active = False
    bot_status.paused = False
    bot_status.last_tick = None


def _poller() -> NotificationPoller:
    poller = NotificationPoller.__new__(NotificationPoller)
    poller.client = Mock()
    poller.client.authenticate = AsyncMock()
    poller.handler = Mock()
    poller._running = True
    poller._background_tasks = set()
    poller._next_alert_watch_poll = float("inf")
    poller._next_relay_watch_poll = float("inf")
    poller._next_review_poll = float("inf")
    poller._seed_schedule_from_history = AsyncMock()
    poller._should_do_daily_post = Mock(return_value=False)
    poller._should_run_cycle = Mock(return_value=False)
    return poller


def test_not_polling_is_503():
    _reset()
    r = client.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unhealthy"
    assert body["polling_active"] is False
    assert body["reason"] == "poller is not running"
    assert body["last_tick_age_s"] is None


def test_fresh_tick_is_200():
    _reset()
    bot_status.polling_active = True
    bot_status.record_tick()
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["reason"] is None
    assert 0 <= body["last_tick_age_s"] < 1


def test_stale_tick_is_503_even_with_polling_active():
    """The regression: a wedged loop keeps polling_active true."""
    _reset()
    bot_status.polling_active = True
    bot_status.last_tick = time.monotonic() - settings.health_stale_after - 1
    r = client.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["polling_active"] is True
    assert body["last_tick_age_s"] > settings.health_stale_after
    assert "last completed poll" in body["reason"]


def test_paused_is_200_and_reported():
    _reset()
    bot_status.paused = True
    bot_status.record_tick()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["paused"] is True


def test_stale_default_covers_more_than_a_few_poll_intervals():
    assert settings.health_stale_after == 30 * settings.notification_poll_interval


async def test_loop_ticks_after_a_completed_notification_check():
    _reset()
    poller = _poller()

    async def stop_after_sleep(_):
        poller._running = False

    with (
        patch.object(poller, "_check_notifications", AsyncMock()),
        patch("bot.services.notification_poller.asyncio.sleep", stop_after_sleep),
    ):
        await poller._poll_loop()
    assert bot_status.last_tick is not None


async def test_swallowed_poll_error_does_not_tick_and_still_sleeps():
    """A raise the loop catches must not count as work, and the loop must
    wait out the interval instead of retrying the failed fetch at once."""
    _reset()
    poller = _poller()
    slept: list[float] = []

    async def stop_after_sleep(delay):
        slept.append(delay)
        poller._running = False

    with (
        patch.object(
            poller, "_check_notifications", AsyncMock(side_effect=RuntimeError("down"))
        ),
        patch("bot.services.notification_poller.asyncio.sleep", stop_after_sleep),
    ):
        await poller._poll_loop()
    assert bot_status.last_tick is None
    assert slept == [settings.notification_poll_interval]


async def test_start_seeds_the_heartbeat():
    """Between start() and the first completed poll (auth, schedule
    seeding) there is no tick yet; start() stamps one so that window
    reads as fresh rather than as never-polled."""
    _reset()
    poller = _poller()
    with patch.object(poller, "_poll_loop", AsyncMock()):
        task = await poller.start()
        await task
    assert bot_status.polling_active is True
    assert bot_status.last_tick is not None
    _reset()


def test_watchdog_decision_matches_health():
    from bot.core import watchdog

    s = BotStatus()
    assert watchdog.stale_reason(s, 300) == "poller is not running"
    s.paused = True
    assert watchdog.stale_reason(s, 300) is None
    s.paused = False
    s.polling_active = True
    s.record_tick()
    assert watchdog.stale_reason(s, 300) is None
    s.last_tick = time.monotonic() - 301
    assert "last completed poll" in (watchdog.stale_reason(s, 300) or "")
    s.paused = True
    assert "last completed poll" in (watchdog.stale_reason(s, 300) or "")


async def test_watchdog_exits_once_when_stale():
    """A 503 alone never recovers phi: fly only restarts an exited
    process. The exit is injected so the suite survives the check."""
    from bot.core import watchdog

    _reset()
    bot_status.polling_active = True
    bot_status.last_tick = time.monotonic() - settings.health_stale_after - 1
    exits: list[int] = []
    await watchdog.run(exit=exits.append, interval=0)
    assert exits == [1]
    _reset()


async def test_watchdog_keeps_waiting_while_fresh():
    from bot.core import watchdog

    _reset()
    bot_status.polling_active = True
    bot_status.record_tick()
    exits: list[int] = []
    task = asyncio.create_task(watchdog.run(exit=exits.append, interval=0))
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert exits == []
    _reset()
