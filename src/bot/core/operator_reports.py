"""Private operator reports: durable delivery receipts and acknowledgement evidence."""

import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.status import bot_status

JOURNAL = Path("/data/operator-reports.sqlite3")
LOCK = asyncio.Lock()


@contextmanager
def connect():
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(JOURNAL)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS reports (
        incident TEXT PRIMARY KEY, attempted REAL NOT NULL, state TEXT NOT NULL,
        convo TEXT, message TEXT, sent REAL, acknowledged REAL)""")
    try:
        with db:
            yield db
    finally:
        db.close()


def chat():
    client = bot_client.client.clone()
    client.request.set_additional_headers(
        {"atproto-proxy": "did:web:api.bsky.chat#bsky_chat"}
    )
    return client.chat.bsky.convo


async def send_report(incident: str, text: str) -> dict:
    """Reserve before delivery; uncertain sends are never automatically repeated."""
    async with LOCK:
        with connect() as db:
            existing = db.execute(
                "SELECT * FROM reports WHERE incident=?", (incident,)
            ).fetchone()
            if existing:
                return dict(existing)
            db.execute(
                "INSERT INTO reports (incident,attempted,state) VALUES (?,?,?)",
                (incident, datetime.now(UTC).timestamp(), "pending"),
            )
        try:
            api = chat()
            conversation = await asyncio.to_thread(
                api.get_convo_for_members, {"members": [settings.owner_did]}
            )
            message = await asyncio.to_thread(
                api.send_message,
                {"convo_id": conversation.convo.id, "message": {"text": text}},
            )
            sent = datetime.fromisoformat(
                message.sent_at.replace("Z", "+00:00")
            ).timestamp()
            with connect() as db:
                db.execute(
                    "UPDATE reports SET state=?,convo=?,message=?,sent=? WHERE incident=?",
                    ("sent", conversation.convo.id, message.id, sent, incident),
                )
        except Exception:
            # The service may have accepted the message before the response failed.
            with connect() as db:
                db.execute(
                    "UPDATE reports SET state=? WHERE incident=?",
                    ("uncertain", incident),
                )
            raise
        return {
            "incident": incident,
            "state": "sent",
            "message": message.id,
            "sent": sent,
        }


async def report_state(incident: str) -> dict:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM reports WHERE incident=?", (incident,)
        ).fetchone()
    if row is None:
        return {"incident": incident, "state": "not-sent"}
    state = dict(row)
    if state["state"] != "sent" or state["acknowledged"]:
        return state
    # Any operator response since the ping stops automatic public escalation.
    # It is evidence of contact, not evidence that the incident is resolved.
    cursor = None
    for _ in range(10):
        params = {"convo_id": state["convo"], "limit": 100}
        if cursor:
            params["cursor"] = cursor
        result = await asyncio.to_thread(chat().get_messages, params)
        for message in result.messages:
            sent_at = getattr(message, "sent_at", None)
            if not sent_at:
                continue
            ts = datetime.fromisoformat(sent_at.replace("Z", "+00:00")).timestamp()
            if ts <= state["sent"]:
                return state
            sender = getattr(message, "sender", None)
            if sender and sender.did == settings.owner_did:
                with connect() as db:
                    db.execute(
                        "UPDATE reports SET acknowledged=? WHERE incident=?",
                        (ts, incident),
                    )
                state["acknowledged"] = ts
                return state
        cursor = result.cursor
        if not cursor:
            return state
    # Incomplete history cannot prove absence of a response.
    return {**state, "state": "history-incomplete"}


def public_eligible(report: dict, now: float, *, open_incident: bool) -> bool:
    """Six hours unanswered permits consideration, never automatic publication."""
    return bool(
        open_incident
        and report.get("state") == "sent"
        and not report.get("acknowledged")
        and report.get("sent")
        and now - report["sent"] >= 6 * 3600
    )


async def delivery_context() -> str:
    """Verified incident delivery state for the public-action judge; no DM bodies."""
    lines = ["Operator reporting: private first. No DM body is public evidence."]
    now = datetime.now(UTC).timestamp()
    for key, incident in bot_status.alert_incidents.items():
        if incident.get("closed_ts"):
            continue
        identity = f"{key}:{incident['opened_ts']}"
        try:
            state = await report_state(identity)
            eligible = public_eligible(state, now, open_incident=True)
            lines.append(
                f"{key} ({incident.get('name', '')}): private={state['state']}; "
                f"operator responded={bool(state.get('acknowledged'))}; "
                f"public escalation eligible={eligible}."
            )
        except Exception:
            lines.append(
                f"{key}: private delivery/response check failed; public escalation ineligible."
            )
    return "\n".join(lines)
