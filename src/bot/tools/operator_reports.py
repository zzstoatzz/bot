"""Report actionable incidents privately to the configured operator."""

import time
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from bot.core import operator_reports
from bot.core.override import get_override, refusal_text
from bot.core.policy import check_action
from bot.status import bot_status
from bot.tools._helpers import PhiDeps


def register(agent):
    @agent.tool_plain
    async def report_operator(
        incident_key: Annotated[
            str, Field(description="Exact incident key from ALERT WATCH")
        ],
        text: Annotated[
            str,
            Field(
                max_length=1000,
                description="Private report and needed action; omit to check delivery",
            ),
        ] = "",
    ) -> dict:
        """Check a private report or send one actionable incident to the operator by DM.

        Report only issues needing their hands. Delivery is recorded once per
        incident opening. An uncertain send must be investigated, never retried
        under another key. Acknowledgement means contact, not resolution.
        Public escalation is only eligible after six unanswered hours and still
        needs a concrete reason to interrupt; eligibility is not an instruction.
        """
        incident = bot_status.alert_incidents.get(incident_key)
        if not incident or incident.get("closed_ts"):
            return {"error": "Incident is absent or closed; no message sent."}
        key = f"{incident_key}:{incident['opened_ts']}"
        try:
            report = await operator_reports.report_state(key)
            if text.strip() and report["state"] == "not-sent":
                override = await get_override()
                if override["active"]:
                    return {"error": refusal_text(override)}
                verdict = await check_action(
                    action=f"Private Bluesky DM to operator: {text}",
                    provenance=f"Operator authorized private-first incident reporting. Incident: {incident}. No prior report for this opening.",
                    tool="report_operator",
                )
                if verdict["verdict"] != "allow":
                    return {"error": "Private report withheld", "verdict": verdict}
                report = await operator_reports.send_report(key, text)
            return {
                **report,
                "public_escalation_eligible": operator_reports.public_eligible(
                    report, time.time(), open_incident=True
                ),
            }
        except Exception:
            return {
                "error": "Private report status unavailable or delivery uncertain. Do not resend or escalate publicly until reconciled."
            }

    @agent.tool
    async def reply_operator_dm(
        ctx: RunContext[PhiDeps],
        text: Annotated[
            str,
            Field(
                min_length=1,
                max_length=1000,
                description="Private reply to the current operator DM",
            ),
        ],
    ) -> dict:
        """Reply privately to the operator in the current DM conversation.

        Silence is valid. One reply per incoming batch; an uncertain delivery is
        held for inspection rather than sent again. Private context stays private.
        """
        if not ctx.deps.private_message_id:
            return {"error": "This tool is only available in an operator DM run."}
        override = await get_override()
        if override["active"]:
            return {"error": refusal_text(override)}
        verdict = await check_action(
            action=f"Private Bluesky reply to operator: {text}",
            provenance=ctx.deps.private_message_context,
            tool="reply_operator_dm",
        )
        if verdict["verdict"] != "allow":
            return {"error": "Private reply withheld", "verdict": verdict}
        try:
            return await operator_reports.send_report(
                f"dm-reply:{ctx.deps.private_message_id}", text
            )
        except Exception:
            return {"error": "Delivery uncertain; do not resend."}
