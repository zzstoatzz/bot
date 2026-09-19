"""A private route to the operator from any run.

2026-09-19. Phi found her cosmik-records skill stale and had a patch. From a
notifications run she had no private channel: reply_operator_dm only works
inside a run the operator's DM started, and report_operator needed an alert
incident key. The operator-reporting policy still told her to go private,
then blocked every public version. She parked the note in memory for a DM
run that only the operator can start.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core import policy
from bot.tools import operator_reports as tool_module
from bot.tools.posting import _build_allowed_handles


@pytest.fixture
def report(monkeypatch):
    registered = {}

    def tool(fn):
        registered[fn.__name__] = fn
        return fn

    tool_module.register(SimpleNamespace(tool=tool, tool_plain=tool))
    monkeypatch.setattr(
        tool_module, "get_override", AsyncMock(return_value={"active": False})
    )
    judge = AsyncMock(return_value={"verdict": "allow"})
    monkeypatch.setattr(tool_module, "check_action", judge)
    monkeypatch.setattr(tool_module.bot_status, "alert_incidents", {})
    sent = []

    async def send_report(key, text):
        sent.append((key, text))
        return {"incident": key, "state": "sent", "message": "m", "sent": 1.0}

    monkeypatch.setattr(tool_module.operator_reports, "send_report", send_report)
    monkeypatch.setattr(
        tool_module.operator_reports,
        "report_state",
        AsyncMock(return_value={"state": "not-sent"}),
    )
    return registered, sent, judge


async def test_a_note_key_sends_without_an_alert_incident(report):
    registered, sent, _ = report
    result = await registered["report_operator"](
        "note:cosmik-skill-stale", "the cosmik-records skill still teaches execute"
    )
    assert result["state"] == "sent"
    assert sent == [
        ("note:cosmik-skill-stale", "the cosmik-records skill still teaches execute")
    ]


async def test_a_note_is_judged_like_any_private_report(report):
    registered, sent, judge = report
    judge.return_value = {"verdict": "block", "reason": "x"}
    result = await registered["report_operator"]("note:x", "text")
    assert "withheld" in result["error"]
    assert sent == []


async def test_an_unknown_incident_key_still_refuses(report):
    registered, sent, _ = report
    result = await registered["report_operator"]("some-alert", "text")
    assert "absent or closed" in result["error"]
    assert sent == []


async def test_dm_reply_outside_a_dm_run_points_at_the_note_route(report):
    registered, _, _ = report
    ctx = SimpleNamespace(deps=SimpleNamespace(private_message_id=""))
    result = await registered["reply_operator_dm"](ctx, "hello")
    assert "report_operator" in result["error"]
    assert "note:" in result["error"]


async def test_judge_is_told_who_the_operator_is(monkeypatch):
    seen = {}

    class Judge:
        async def run(self, prompt):
            seen["prompt"] = prompt
            return SimpleNamespace(
                output={"verdict": "allow", "policy": "", "reason": ""}
            )

    monkeypatch.setattr(policy, "_get_judge", lambda: Judge())
    await policy.check_action(action="reply: hi", provenance="p")
    prompt = seen["prompt"]
    for handle in policy.settings.operator_handles:
        assert f"@{handle}" in prompt
    for did in policy.settings.operator_dids:
        assert did in prompt


async def test_operator_handles_are_always_mentionable(monkeypatch):
    from bot.tools import posting

    monkeypatch.setattr(
        posting, "get_mentionable_handles", AsyncMock(return_value=set())
    )
    allowed = await _build_allowed_handles()
    assert set(policy.settings.operator_handles) <= allowed
