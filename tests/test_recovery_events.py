from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastmcp import Client
from fastmcp_events.models import EventOccurrence, PollEventsResult

from bot.core import operator_reports
from bot.services import recovery_events

ENDPOINT = "http://100.96.216.23:9012/phi/mcp"


class StubClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


@pytest.fixture
def event(tmp_path, monkeypatch):
    monkeypatch.setattr(operator_reports, "JOURNAL", tmp_path / "report.sqlite3")
    monkeypatch.setattr(recovery_events, "available", AsyncMock(return_value=True))
    return EventOccurrence(
        name=recovery_events.EVENT_NAME,
        eventId=str(uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        data={
            "machine": "abc123",
            "attempts": 10,
            "oom_killed": False,
            "exit_code": 1,
            "failed_at": datetime.now(UTC).isoformat(),
        },
    )


def test_requires_private_transport_and_scoped_path():
    assert recovery_events.allowed_endpoint(ENDPOINT)
    assert recovery_events.allowed_endpoint("https://example.com/phi/mcp")
    assert not recovery_events.allowed_endpoint("http://example.com/phi/mcp")
    assert not recovery_events.allowed_endpoint("http://100.96.216.23:9012/mcp")
    assert not recovery_events.allowed_endpoint(
        "https://example.com/phi/mcp?token=secret"
    )


async def test_bootstrap_and_replay_deliver_one_private_report(event, monkeypatch):
    probe = AsyncMock(return_value=503)
    judge = AsyncMock(return_value={"verdict": "allow"})
    monkeypatch.setattr(recovery_events, "current_health", probe)
    monkeypatch.setattr(recovery_events, "check_action", judge)
    key = f"note:recovery-{event.event_id}"
    sent = []

    async def send_report(incident, text):
        sent.append((incident, text))
        with operator_reports.connect() as db:
            db.execute(
                "INSERT INTO reports (incident, attempted, state) VALUES (?, 0, 'sent')",
                (incident,),
            )
        return {"state": "sent"}

    async def poll(_, name, *, cursor, max_events):
        assert name == recovery_events.EVENT_NAME and max_events == 1
        return PollEventsResult(
            events=[event] if cursor else [],
            cursor="after" if cursor else "start",
            next_poll_ms=15_000,
        )

    monkeypatch.setattr(operator_reports, "send_report", send_report)
    monkeypatch.setattr(recovery_events, "poll_events_mcp", poll)
    await recovery_events.poll_once(ENDPOINT, cast(Client, StubClient()))
    assert not sent and recovery_events.checkpoint(ENDPOINT) == "start"
    await recovery_events.poll_once(ENDPOINT, cast(Client, StubClient()))
    await recovery_events.poll_once(ENDPOINT, cast(Client, StubClient()))
    assert recovery_events.checkpoint(ENDPOINT) == "after"
    ((incident, text),) = sent
    assert incident == key
    assert "Pollz still returned HTTP 503" in text
    assert "10 Cellar restart retries" in text
    assert "last crash log" in text
    probe.assert_awaited_once()
    judge.assert_awaited_once()


async def test_retains_cursor_if_reporting_must_wait_and_skips_recovered_incident(
    event, monkeypatch
):
    poll = AsyncMock(
        return_value=PollEventsResult(
            events=[event], cursor="after", next_poll_ms=15_000
        )
    )
    probe = AsyncMock(side_effect=[503, 200])
    judge = AsyncMock(return_value={"verdict": "allow"})
    sender = AsyncMock()
    monkeypatch.setattr(recovery_events, "poll_events_mcp", poll)
    monkeypatch.setattr(recovery_events, "current_health", probe)
    monkeypatch.setattr(recovery_events, "check_action", judge)
    monkeypatch.setattr(operator_reports, "send_report", sender)
    monkeypatch.setattr(
        recovery_events, "available", AsyncMock(side_effect=[True, False, True])
    )
    recovery_events.checkpoint(ENDPOINT, "start")
    await recovery_events.poll_once(ENDPOINT, cast(Client, StubClient()))
    assert recovery_events.checkpoint(ENDPOINT) == "start"
    await recovery_events.poll_once(ENDPOINT, cast(Client, StubClient()))
    assert recovery_events.checkpoint(ENDPOINT) == "after"
    sender.assert_not_awaited()
    judge.assert_awaited_once()
