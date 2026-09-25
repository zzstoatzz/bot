import asyncio

from bot.services import notification_poller as module
from bot.services.notification_poller import NotificationPoller


async def test_bio_refresh_is_background_recurring_and_never_overlaps(monkeypatch):
    poller = object.__new__(NotificationPoller)
    poller._bio_task = None
    poller._next_bio_refresh = 0
    poller._background_tasks = set()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def work():
        calls.append(True)
        started.set()
        await release.wait()

    monkeypatch.setattr(poller, "_refresh_bio", work)
    monkeypatch.setattr(module.bot_status, "paused", False)
    monkeypatch.setattr(module.settings, "voice_reset", False)
    poller._schedule_bio_refresh()
    await asyncio.wait_for(started.wait(), 1)
    first = poller._bio_task
    assert first is not None and not first.done()
    poller._schedule_bio_refresh()
    assert poller._bio_task is first
    poller._next_bio_refresh = 0
    poller._schedule_bio_refresh()
    assert poller._bio_task is first
    release.set()
    await first
    poller._schedule_bio_refresh()
    assert poller._bio_task is not None
    await poller._bio_task
    assert len(calls) == 2


async def test_paused_bio_refresh_stays_due_until_resume(monkeypatch):
    poller = object.__new__(NotificationPoller)
    poller._bio_task = None
    poller._next_bio_refresh = 0
    monkeypatch.setattr(module.bot_status, "paused", True)
    poller._schedule_bio_refresh()
    assert poller._bio_task is None
    assert poller._next_bio_refresh == 0
