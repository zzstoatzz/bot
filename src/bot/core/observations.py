"""Phi's active observations — small, rotating attention pool.

Each observation is a record under `io.zzstoatzz.phi.observation` on phi's
PDS. The pool is bounded (ACTIVE_CAP); when phi records a new observation
beyond the cap, the oldest is archived to a turbopuffer namespace
(`phi-observations`) where it stays searchable but no longer appears in the
prompt.

Two paths leave the active pool:
- aged out: count exceeds cap, oldest goes to archive with reason
- explicit drop: phi calls drop_observation(rkey, reason)

Both archive to the same namespace with `archival_reason` recording why.
The archive is append-only and not surfaced by default; a future tool can
search it for "did i already think about this last week."

Reasoning is optional but encouraged at write time — what made phi notice
this, what might compose with it, why it's worth attention.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

from bot.core.atproto_client import BotClient

if TYPE_CHECKING:
    from bot.memory import NamespaceMemory

logger = logging.getLogger("bot.observations")

OBSERVATION_COLLECTION = "io.zzstoatzz.phi.observation"
ARCHIVE_NAMESPACE = "phi-observations"
ACTIVE_CAP = 5


class ObservationRecord(TypedDict):
    rkey: str
    content: str
    reasoning: str
    created_at: str


async def list_active(client: BotClient) -> list[ObservationRecord]:
    """List all active observation records, oldest first.

    Sorted by rkey ascending — TIDs are time-ordered so this is creation
    order. Used both for prompt rendering and for the archive-on-overflow
    decision (oldest goes to archive).
    """
    await client.authenticate()
    if not client.client.me:
        return []
    try:
        response = client.client.com.atproto.repo.list_records(
            {
                "repo": client.client.me.did,
                "collection": OBSERVATION_COLLECTION,
                "limit": 50,
            }
        )
    except Exception as e:
        logger.debug(f"list observations failed: {e}")
        return []

    rows: list[ObservationRecord] = []
    for rec in response.records or []:
        value = dict(rec.value) if rec.value else {}
        rows.append(
            ObservationRecord(
                rkey=rec.uri.split("/")[-1],
                content=value.get("content", ""),
                reasoning=value.get("reasoning", "") or "",
                created_at=value.get("created_at", ""),
            )
        )
    rows.sort(key=lambda r: r["rkey"])
    return rows


async def _archive(
    memory: NamespaceMemory | None,
    record: ObservationRecord,
    archival_reason: str,
) -> None:
    """Move an observation row into the archive namespace.

    Embedded by content. If memory is unavailable (no turbopuffer), the
    record is dropped silently — the active-pool deletion still happens
    in the caller, so we just lose the historical trace.
    """
    if memory is None:
        logger.debug("archive: no memory client, skipping archive write")
        return
    try:
        ns = memory.client.namespace(ARCHIVE_NAMESPACE)
        embedding = await memory._get_embedding(record["content"])
        ns.write(
            upsert_rows=[
                {
                    "id": record["rkey"],
                    "vector": embedding,
                    "content": record["content"],
                    "reasoning": record["reasoning"],
                    "archival_reason": archival_reason,
                    "created_at": record["created_at"],
                    "archived_at": datetime.now(UTC).isoformat(),
                }
            ],
            distance_metric="cosine_distance",
            schema={
                "content": {"type": "string", "full_text_search": True},
                "reasoning": {"type": "string"},
                "archival_reason": {"type": "string", "filterable": True},
                "created_at": {"type": "string"},
                "archived_at": {"type": "string"},
            },
        )
    except Exception as e:
        logger.warning(f"archive write failed for {record['rkey']}: {e}")


async def _delete_record(client: BotClient, rkey: str) -> None:
    assert client.client.me is not None
    try:
        client.client.com.atproto.repo.delete_record(
            data={
                "repo": client.client.me.did,
                "collection": OBSERVATION_COLLECTION,
                "rkey": rkey,
            }
        )
    except Exception as e:
        logger.warning(f"delete observation {rkey} failed: {e}")


async def record_observation(
    client: BotClient,
    memory: NamespaceMemory | None,
    content: str,
    reasoning: str = "",
) -> str:
    """Create a new active observation. Returns the record's AT-URI.

    If the active count exceeds ACTIVE_CAP after this write, the oldest
    observation is archived (reason: 'aged out') and removed from the
    active pool — keeping the prompt block bounded.
    """
    await client.authenticate()
    assert client.client.me is not None
    now = datetime.now(UTC).isoformat()
    record = {
        "content": content,
        "reasoning": reasoning,
        "created_at": now,
    }
    result = client.client.com.atproto.repo.create_record(
        data={
            "repo": client.client.me.did,
            "collection": OBSERVATION_COLLECTION,
            "record": record,
        }
    )

    # roll off oldest if we exceeded the cap
    active = await list_active(client)
    overflow = len(active) - ACTIVE_CAP
    for stale in active[:overflow] if overflow > 0 else []:
        await _archive(memory, stale, archival_reason="aged out")
        await _delete_record(client, stale["rkey"])
        logger.info(f"observation aged out: {stale['rkey']} ({stale['content'][:60]})")

    return result.uri


async def drop_observation(
    client: BotClient,
    memory: NamespaceMemory | None,
    rkey: str,
    reason: str,
) -> bool:
    """Explicitly remove an active observation. Archived with reason.

    Returns True if the record existed and was removed, False if not found.
    """
    active = await list_active(client)
    target = next((r for r in active if r["rkey"] == rkey), None)
    if target is None:
        return False
    await _archive(memory, target, archival_reason=reason or "dropped")
    await _delete_record(client, rkey)
    logger.info(f"observation dropped: {rkey} ({reason})")
    return True
