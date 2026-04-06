"""Curiosity queue — PDS-backed work items for phi's background exploration.

Stored as individual records on phi's PDS at:
  at://{did}/io.zzstoatzz.phi.curiosityQueue/{tid}

Lifecycle: pending → in_progress → completed | failed
"""

import logging
from datetime import UTC, datetime

from bot.core.atproto_client import bot_client

logger = logging.getLogger("bot.curiosity_queue")

COLLECTION = "io.zzstoatzz.phi.curiosityQueue"


async def _list_records() -> list:
    """List all queue records. Returns empty list if collection doesn't exist."""
    await bot_client.authenticate()
    assert bot_client.client.me is not None
    try:
        result = bot_client.client.com.atproto.repo.list_records(
            {"repo": bot_client.client.me.did, "collection": COLLECTION, "limit": 50}
        )
        return result.records
    except Exception:
        return []


def _rkey(record) -> str:
    return record.uri.split("/")[-1]


async def _update_status(record, status: str) -> dict:
    """Update a record's status and return the updated value."""
    assert bot_client.client.me is not None
    value = dict(record.value)
    value["status"] = status
    value["updatedAt"] = datetime.now(UTC).isoformat()
    bot_client.client.com.atproto.repo.put_record(
        data={
            "repo": bot_client.client.me.did,
            "collection": COLLECTION,
            "rkey": _rkey(record),
            "record": value,
        }
    )
    return value


async def enqueue(
    kind: str,
    subject: str,
    source: str,
    source_uri: str | None = None,
) -> bool:
    """Create a pending queue record. Returns False if a duplicate pending/in_progress item exists."""
    records = await _list_records()

    # deduplicate: skip if pending or in_progress item with same kind+subject exists
    for rec in records:
        val = rec.value
        if (
            val.get("kind") == kind
            and val.get("subject") == subject
            and val.get("status") in ("pending", "in_progress")
        ):
            logger.debug(f"duplicate queue item: {kind} {subject}")
            return False

    assert bot_client.client.me is not None
    now = datetime.now(UTC).isoformat()
    record = {
        "$type": COLLECTION,
        "kind": kind,
        "subject": subject,
        "source": source,
        "status": "pending",
        "createdAt": now,
        "updatedAt": now,
    }
    if source_uri:
        record["sourceUri"] = source_uri

    bot_client.client.com.atproto.repo.create_record(
        {"repo": bot_client.client.me.did, "collection": COLLECTION, "record": record}
    )
    logger.info(f"enqueued: {kind} {subject} (source={source})")
    return True


async def claim() -> tuple[dict, str] | None:
    """Claim the oldest pending item by marking it in_progress.

    Returns (record_value, rkey) or None if queue is empty.
    """
    records = await _list_records()

    pending = [r for r in records if r.value.get("status") == "pending"]
    if not pending:
        return None

    # oldest = last in list (list_records returns newest first)
    oldest = pending[-1]
    value = await _update_status(oldest, "in_progress")
    rkey = _rkey(oldest)
    logger.info(f"claimed: {value.get('kind')} {value.get('subject')}")
    return value, rkey


async def complete(rkey: str) -> None:
    """Mark a claimed item as completed."""
    records = await _list_records()
    for rec in records:
        if _rkey(rec) == rkey:
            await _update_status(rec, "completed")
            logger.info(
                f"completed: {rec.value.get('kind')} {rec.value.get('subject')}"
            )
            return


async def fail(rkey: str) -> None:
    """Mark a claimed item as failed."""
    records = await _list_records()
    for rec in records:
        if _rkey(rec) == rkey:
            await _update_status(rec, "failed")
            logger.warning(
                f"failed: {rec.value.get('kind')} {rec.value.get('subject')}"
            )
            return


async def list_pending(limit: int = 10) -> list[dict]:
    """List pending queue items for inspection."""
    records = await _list_records()
    pending = [dict(r.value) for r in records if r.value.get("status") == "pending"]
    return pending[:limit]
