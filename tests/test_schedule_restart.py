"""A restart must not re-run a scheduled slot that already ran, posted or not."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot import status
from bot.services import notification_poller as module
from bot.services.notification_poller import NotificationPoller

TZ = ZoneInfo("America/Chicago")


def _restart(monkeypatch, tmp_path, now: datetime) -> NotificationPoller:
    """A new process: status reloaded from disk, poller state empty."""
    monkeypatch.setattr(status, "STATUS_FILE", tmp_path / "status.json")
    fresh = status.BotStatus()
    fresh._load()
    monkeypatch.setattr(module, "bot_status", fresh)
    monkeypatch.setattr(module, "_now_local", lambda: now)
    monkeypatch.setattr(module, "_operator_tz", lambda: TZ)
    monkeypatch.setattr(module.settings, "daily_reflection_hour", 14)
    monkeypatch.setattr(module.settings, "thought_post_hours", [9, 13, 17, 21])
    return NotificationPoller.__new__(NotificationPoller)


def test_reflection_that_did_not_post_is_not_rerun_after_restart(monkeypatch, tmp_path):
    reflected = datetime(2026, 11, 1, 14, 0, tzinfo=TZ)
    poller = _restart(monkeypatch, tmp_path, reflected)
    assert poller._should_do_daily_post()
    module.bot_status.record_daily_reflection(reflected)

    poller = _restart(monkeypatch, tmp_path, reflected + timedelta(hours=1, minutes=48))
    assert not poller._should_do_daily_post()

    poller = _restart(monkeypatch, tmp_path, reflected + timedelta(days=1))
    assert poller._should_do_daily_post()


def test_cycle_slot_is_not_rerun_after_restart(monkeypatch, tmp_path):
    slot = datetime(2026, 11, 1, 17, 2, tzinfo=TZ)
    poller = _restart(monkeypatch, tmp_path, slot)
    assert poller._should_run_cycle()
    module.bot_status.record_cycle(slot)

    poller = _restart(monkeypatch, tmp_path, slot + timedelta(minutes=30))
    assert not poller._should_run_cycle()

    poller = _restart(monkeypatch, tmp_path, slot + timedelta(hours=4))
    assert poller._should_run_cycle()


def test_unknown_history_counts_current_slots_as_run(monkeypatch, tmp_path):
    now = datetime(2026, 11, 1, 17, 30, tzinfo=TZ)
    poller = _restart(monkeypatch, tmp_path, now)
    module.bot_status.assume_schedule_ran(now)
    assert not poller._should_do_daily_post()
    assert not poller._should_run_cycle()

    poller = _restart(monkeypatch, tmp_path, now + timedelta(hours=4))
    assert poller._should_run_cycle()
