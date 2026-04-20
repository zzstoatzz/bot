"""Tests for the canonical relative_when helper used across system prompt blocks."""

from datetime import UTC, datetime, timedelta

from bot.utils.time import relative_when


def _ago(delta: timedelta) -> str:
    """Build an ISO timestamp N seconds/minutes/etc in the past."""
    return (datetime.now(UTC) - delta).isoformat()


def test_seconds():
    assert relative_when(_ago(timedelta(seconds=5))) == "5s ago"


def test_seconds_at_boundary():
    # 59s should still be seconds
    s = relative_when(_ago(timedelta(seconds=59)))
    assert s.endswith("s ago")


def test_minutes():
    assert relative_when(_ago(timedelta(minutes=15))) == "15m ago"


def test_hours_under_10_has_decimal():
    # 1.5h should show one decimal
    s = relative_when(_ago(timedelta(hours=1, minutes=30)))
    assert s.endswith("h ago")
    assert "." in s


def test_hours_over_10_no_decimal():
    s = relative_when(_ago(timedelta(hours=15)))
    assert s.endswith("h ago")
    assert "." not in s


def test_days_under_10_has_decimal():
    s = relative_when(_ago(timedelta(days=2, hours=12)))
    assert s.endswith("d ago")
    assert "." in s


def test_days_over_10_no_decimal():
    s = relative_when(_ago(timedelta(days=15)))
    assert s.endswith("d ago")
    assert "." not in s


def test_months():
    s = relative_when(_ago(timedelta(days=60)))
    assert s.endswith("mo ago")
    assert s.startswith("2")


def test_years():
    s = relative_when(_ago(timedelta(days=400)))
    assert s.endswith("y ago")
    assert s.startswith("1")


def test_future_returns_empty():
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert relative_when(future) == ""


def test_invalid_returns_empty():
    assert relative_when("not a timestamp") == ""


def test_empty_returns_empty():
    assert relative_when("") == ""


def test_z_suffix_handled():
    # "2026-04-19T12:00:00Z" form (Z suffix) should parse
    z_form = (
        (datetime.now(UTC) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    )
    s = relative_when(z_form)
    assert s.endswith("m ago")
