"""Original notification events, captured before generation.

Capture original notifications before hydration or target-keyed batching.
Interpretations and processing outcomes are separate from these event facts.
"""

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Literal, TypedDict

from atproto import models
from turbopuffer import NotFoundError, Turbopuffer

ENCOUNTER_NAMESPACE = "phi-encounters"
logger = logging.getLogger("bot.memory.encounters")
ENCOUNTER_SCHEMA = {
    "content": {"type": "string", "full_text_search": True},
    "event_ids": {"type": "[]string"},
    "recorded_at": {"type": "string"},
}


def indexed_time(value: str) -> str:
    """Normalize the notification index timestamp for ordered string queries."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("notification index time must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds")


class Encounter(TypedDict):
    id: str
    kind: str
    actor_did: str
    actor_handle: str
    event_uri: str
    event_cid: str
    reason: str
    subject_uri: str
    source_created_at: str
    indexed_at: str
    captured_at: str
    content: str
    record_json: str
    source_uris: list[str]


def notification_event_id(notification) -> str:
    """A stable key for this delivered record version and notification reason."""
    identity = json.dumps([notification.uri, notification.cid, notification.reason])
    return hashlib.sha256(identity.encode()).hexdigest()


def notification_encounter(
    notification: models.AppBskyNotificationListNotifications.Notification,
    captured_at: datetime,
) -> Encounter:
    """Preserve a delivered event without needing its subject to remain online."""
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("capture time must include a timezone")
    record = notification.model_dump(mode="json", by_alias=True)["record"]
    # A changed CID is a new record version; later delivery time is not.
    subject = notification.reason_subject or ""
    refs = [notification.uri]
    if subject:
        refs.append(subject)
    reply = record.get("reply") or {}
    for name in ("parent", "root"):
        ref = reply.get(name) or {}
        if uri := ref.get("uri"):
            refs.append(uri)
    return Encounter(
        id=notification_event_id(notification),
        kind="encounter",
        actor_did=notification.author.did,
        actor_handle=notification.author.handle,
        event_uri=notification.uri,
        event_cid=notification.cid,
        reason=notification.reason,
        subject_uri=subject,
        source_created_at=record.get("createdAt") or "",
        indexed_at=indexed_time(notification.indexed_at),
        captured_at=captured_at.astimezone(UTC).isoformat(),
        content=record.get("text") or "",
        record_json=json.dumps(record, ensure_ascii=False, sort_keys=True),
        source_uris=list(dict.fromkeys(refs)),
    )


async def append_encounters(
    client: Turbopuffer, namespace: str, encounters: list[Encounter]
) -> int:
    """Insert original events once, preserving the first capture on replay.

    No embeddings or generation are needed to capture an event. Let write
    failures reach the caller; a failed capture must not look like success.
    Namespace choice is explicit while the migration remains unconnected.
    """
    if not encounters:
        return 0
    unique: dict[str, Encounter] = {}
    for encounter in encounters:
        unique.setdefault(encounter["id"], encounter)
    result = await asyncio.to_thread(
        client.namespace(namespace).write,
        upsert_rows=list(unique.values()),
        upsert_condition=["id", "Eq", None],
        schema=ENCOUNTER_SCHEMA,
    )
    return result.rows_affected


class RecentEncounters(TypedDict):
    status: Literal["ok", "not_initialized", "unavailable"]
    since: str
    until: str
    rows: list[dict]
    has_more: bool


async def read_recent_encounters(
    client: Turbopuffer,
    namespace: str,
    *,
    since: datetime,
    until: datetime,
    limit: int = 10,
    actor_did: str | None = None,
) -> RecentEncounters:
    """Read by notification index time, not by when a recovery scan stored it."""
    if any(t.tzinfo is None or t.utcoffset() is None for t in (since, until)):
        raise ValueError("notification index window must include timezones")
    if since > until or not 1 <= limit <= 100:
        raise ValueError("invalid notification index window or result limit")
    start, end = (
        t.astimezone(UTC).isoformat(timespec="microseconds") for t in (since, until)
    )
    filters: list = [["indexed_at", "Gte", start], ["indexed_at", "Lte", end]]
    if actor_did:
        filters.append(["actor_did", "Eq", actor_did])
    result = RecentEncounters(
        status="ok", since=start, until=end, rows=[], has_more=False
    )
    try:
        response = await asyncio.to_thread(
            client.namespace(namespace).query,
            rank_by=("indexed_at", "desc"),
            filters=["And", filters],
            top_k=limit + 1,
            include_attributes=True,
        )
        rows = response.rows or []
        result["rows"] = [row.model_dump() for row in rows[:limit]]
        result["has_more"] = len(rows) > limit
    except NotFoundError:
        result["status"] = "not_initialized"
    except Exception as e:
        logger.warning(f"encounter history read failed: {e}")
        result["status"] = "unavailable"
    return result


def render_recent_encounters(result: RecentEncounters) -> str:
    """Render received events without implying a response or a decision."""
    if result["status"] == "unavailable":
        return "[RECENT ENCOUNTERS] storage read failed; recent history is unavailable."
    if result["status"] == "not_initialized":
        return "[RECENT ENCOUNTERS] encounter capture has no stored history yet. Older memory may exist elsewhere."
    rows = result["rows"]
    lines = [
        f"[RECENT ENCOUNTERS — notification index time {result['since']} through {result['until']}; "
        f"{len(rows)} shown, newest indexed first"
        f"{'; more records in this window' if result['has_more'] else ''}. "
        "Received events; responses and decisions are not represented here.]"
    ]
    if not rows:
        lines.append("No captured encounters in this window.")
    for row in rows:
        lines.append(
            f"- encounter {row['id']}: @{row['actor_handle']} ({row['actor_did']}): {row['reason']}; "
            f"indexed {row['indexed_at']}; captured {row['captured_at']}; source created "
            f"{row.get('source_created_at') or 'unknown'}"
        )
        if content := row.get("content"):
            preview = content if len(content) <= 240 else content[:239] + "…"
            lines.append(f"  source text: {json.dumps(preview, ensure_ascii=False)}")
        lines.extend(f"  source: {uri}" for uri in row.get("source_uris", []))
    return "\n".join(lines)
