from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bot.core import operator_reports as reports


@pytest.fixture
def journal(tmp_path, monkeypatch):
    monkeypatch.setattr(reports, "JOURNAL", tmp_path / "reports.sqlite3")


async def test_uncertain_send_is_not_repeated(journal, monkeypatch):
    api = SimpleNamespace(
        get_convo_for_members=Mock(
            return_value=SimpleNamespace(convo=SimpleNamespace(id="c"))
        ),
        send_message=Mock(side_effect=TimeoutError),
    )
    monkeypatch.setattr(reports, "chat", lambda: api)
    with pytest.raises(TimeoutError):
        await reports.send_report("incident:1", "needs attention")
    result = await reports.send_report("incident:1", "retry")
    assert result["state"] == "uncertain"
    api.send_message.assert_called_once()
    assert not reports.public_eligible(result, 9999999999, open_incident=True)


async def test_operator_response_stops_escalation(journal, monkeypatch):
    with reports.connect() as db:
        db.execute(
            "INSERT INTO reports VALUES (?,?,?,?,?,?,?)",
            ("incident:1", 1, "sent", "c", "m", 1, None),
        )
    api = SimpleNamespace(
        get_messages=Mock(
            return_value=SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        sent_at="1970-01-01T00:00:02Z",
                        sender=SimpleNamespace(did=reports.settings.owner_did),
                    )
                ],
                cursor=None,
            )
        )
    )
    monkeypatch.setattr(reports, "chat", lambda: api)
    result = await reports.report_state("incident:1")
    assert result["acknowledged"] == 2
    assert not reports.public_eligible(result, 9999999999, open_incident=True)
    assert (await reports.report_state("incident:other"))["state"] == "not-sent"


def test_public_escalation_requires_open_delivered_unanswered_report():
    report = {"state": "sent", "sent": 100, "acknowledged": None}
    assert not reports.public_eligible(report, 101, open_incident=True)
    assert reports.public_eligible(report, 21700, open_incident=True)
    assert not reports.public_eligible(report, 21700, open_incident=False)
    assert not reports.public_eligible(
        {**report, "state": "history-incomplete"}, 21700, open_incident=True
    )
