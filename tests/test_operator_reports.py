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


async def test_incoming_operator_messages_are_deduplicated(journal, monkeypatch):
    with reports.connect() as db:
        db.execute(
            "INSERT INTO reports VALUES (?,?,?,?,?,?,?)",
            ("incident:1", 1, "sent", "c", "m", 1, None),
        )

    def message(id, author, second):
        return SimpleNamespace(
            id=id,
            text=id,
            sender=SimpleNamespace(did=author),
            sent_at=f"1970-01-01T00:00:0{second}Z",
        )

    api = SimpleNamespace(
        get_convo_availability=Mock(
            return_value=SimpleNamespace(convo=SimpleNamespace(id="c"))
        ),
        get_messages=Mock(
            return_value=SimpleNamespace(
                messages=[
                    message("incoming", reports.settings.owner_did, 3),
                    message("ours", "did:plc:phi", 2),
                    message("old", reports.settings.owner_did, 0),
                ],
                cursor=None,
            )
        ),
    )
    monkeypatch.setattr(reports, "chat", lambda: api)
    history, ids = await reports.incoming_messages()
    assert ids == ["incoming"]
    assert [m["id"] for m in history] == ["ours", "incoming"]
    reports.mark_messages_handled(ids)
    assert await reports.incoming_messages() == ([], [])


async def test_private_entrypoint_does_not_supply_public_memory():
    from unittest.mock import AsyncMock

    from bot.agent import PhiAgent

    agent = PhiAgent.__new__(PhiAgent)
    agent._run_agent = AsyncMock(return_value="quietly completed")
    await agent.process_operator_dm("No reply needed.", "message")
    call = agent._run_agent.await_args.kwargs
    assert call["deps"].memory is None
    assert call["deps"].private_message_id == "message"
    assert "No reply needed." in call["prompt"]


def test_conversation_preserves_speaker_and_new_turn():
    import json

    history = [
        {"id": "old", "author": "did:plc:phi", "sent": 1, "text": "No reply needed."},
        {
            "id": "new",
            "author": reports.settings.owner_did,
            "sent": 2,
            "text": "hey buddy",
        },
    ]
    material = json.loads(reports.conversation_material(history, ["new"]))
    assert material["messages"][0]["speaker"] == "phi"
    assert not material["messages"][0]["new_incoming"]
    assert material["messages"][1]["speaker"] == "operator"
    assert material["messages"][1]["new_incoming"]
