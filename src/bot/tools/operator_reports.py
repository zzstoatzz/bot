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

REPORT_CAP = 300


def register(agent):
    @agent.tool_plain
    async def report_operator(
        incident_key: Annotated[
            str,
            Field(
                description=(
                    "Exact incident key from ALERT WATCH, or note:<slug> for "
                    "anything that has no alert (a stale doc, a blocked route)"
                )
            ),
        ],
        text: Annotated[
            str,
            Field(
                description=(
                    "What you need from the operator and the observed fact behind "
                    f"it, at most {REPORT_CAP} characters; omit to check delivery"
                ),
            ),
        ] = "",
    ) -> dict:
        """Send one private message to the operator by DM, or check its delivery.

        The operator reads this on a phone between other things, so it is the
        size of a post: what you need from them, and the one observed fact that
        makes it worth the interruption. They will ask for the rest. How you
        found it, what you tried, what it might mean, and what you are unsure
        of stay in memory and logs, with tool names, record IDs, and approval
        mechanics. A permission request is one question plus any material scope
        or risk; do not prescribe reply wording. Reuse the same key for the
        same work; a new key does not justify repeating an unchanged request.
        Report only issues needing their hands. An alert incident is keyed
        by its opening; anything else takes a note: key you choose, sent
        once per key. An uncertain send must be investigated, never retried
        under another key. Acknowledgement means contact, not resolution.
        Public escalation is only eligible after six unanswered hours and still
        needs a concrete reason to interrupt; eligibility is not an instruction.
        """
        if incident_key.startswith("note:"):
            incident = {"note": incident_key}
            key = incident_key
        else:
            incident = bot_status.alert_incidents.get(incident_key)
            if not incident or incident.get("closed_ts"):
                return {
                    "error": "Incident is absent or closed; no message sent. "
                    "For something without an alert, use a note:<slug> key."
                }
            key = f"{incident_key}:{incident['opened_ts']}"
        if len(text) > REPORT_CAP:
            return {
                "error": f"not sent — compress first: text is {len(text)} chars "
                f"(max {REPORT_CAP}). keep the ask and the one fact behind it; "
                "the reasoning goes in a memory, and the operator will ask if "
                "they want it."
            }
        try:
            report = await operator_reports.report_state(key)
            if text.strip() and report["state"] == "not-sent":
                override = await get_override()
                if override["active"]:
                    return {"error": refusal_text(override)}
                history = await operator_reports.recent_conversation()
                verdict = await check_action(
                    action=f"Private Bluesky DM to operator: {text}",
                    provenance=(
                        f"Operator authorized private-first incident reporting. Incident: {incident}. "
                        "No prior receipt for this key; the same work may already have been reported. "
                        f"Recent private conversation: {history}"
                    ),
                    tool="report_operator",
                )
                if verdict["verdict"] != "allow":
                    return {"error": "Private report withheld", "verdict": verdict}
                report = await operator_reports.send_report(key, text)
            return {
                **report,
                "public_escalation_eligible": operator_reports.public_eligible(
                    report, time.time(), open_incident="note" not in incident
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
        The answer to what they asked is the first sentence, and usually the
        whole reply. Go past a sentence or two only when they asked for an
        explanation, and then only as far as the question reaches. Tool names,
        request keys, IDs, and approval mechanics stay out unless they asked
        for them or need them to act.
        """
        if not ctx.deps.private_message_id:
            return {
                "error": "This tool only answers an operator DM. To reach the "
                "operator from here, use report_operator with a note:<slug> key."
            }
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
