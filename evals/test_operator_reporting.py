"""Classifier channel and escalation regressions; no messages are delivered."""

from unittest.mock import AsyncMock

import pytest

from bot.core import etiquette, operator_reports, policy


@pytest.mark.parametrize(
    "tool,action,context,expected",
    [
        (
            "report_operator",
            "Private Bluesky DM: The worker needs your credential rotation.",
            "Open incident requires operator action; private reporting authorized.",
            "allow",
        ),
        (
            "post",
            "Public post to operator: Please check the failed worker.",
            "worker: private=not-sent; public escalation eligible=False.",
            "block",
        ),
        (
            "post",
            "Public post to operator: The worker is still down; please check my private report.",
            "worker: private=sent eight hours ago; operator responded=False; "
            "public escalation eligible=True. Unresolved credential failure requires "
            "operator action; no prior public ping.",
            "allow",
        ),
        (
            "post",
            "Public post to operator: The worker is still down; check my private report.",
            "worker: private=sent; operator responded=True; public escalation eligible=False.",
            "block",
        ),
    ],
)
async def test_reporting_channel(tool, action, context, expected, tmp_path, monkeypatch):
    monkeypatch.setattr(etiquette, "JOURNAL", tmp_path / "attempts.sqlite3")
    monkeypatch.setattr(
        operator_reports, "delivery_context", AsyncMock(return_value=context)
    )
    verdict = await policy.check_action(
        action, "Operational incident requiring operator credential rotation.", tool=tool
    )
    assert verdict["verdict"] == expected, verdict
