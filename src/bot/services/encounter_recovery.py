"""Recover visible notification history without dispatching public actions."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from turbopuffer import NotFoundError, Turbopuffer

from bot.core.atproto_client import BotClient
from bot.memory.encounters import (
    append_encounters,
    indexed_time,
    notification_encounter,
)
from bot.services.notification_history import notification_pages

# an event indexed shortly before a scan started may not have been listed yet
_LISTING_LAG = timedelta(minutes=10)


async def covered_until(storage: Turbopuffer, namespace: str) -> str:
    """Events indexed before this time were stored by a completed scan.

    A completed scan reached either the end of the history or this bound from
    an earlier completed scan, so coverage below it is contiguous.
    """
    try:
        result = await asyncio.to_thread(
            storage.namespace(namespace).query,
            filters=(
                "And",
                [("kind", "Eq", "encounter_scan"), ("status", "Eq", "completed")],
            ),
            rank_by=("started_at", "desc"),
            top_k=1,
            include_attributes=["started_at"],
        )
    except NotFoundError:
        return ""
    rows = result.rows or []
    if not rows:
        return ""
    started = datetime.fromisoformat(rows[0].model_dump()["started_at"])
    return indexed_time((started - _LISTING_LAG).isoformat())


async def recover_encounters(
    client: BotClient,
    storage: Turbopuffer,
    namespace: str,
    *,
    max_pages: int = 100,
) -> dict:
    """Store each page before advancing and record the traversal's outcome.

    Always start from the newest visible page, independently of UI read state,
    and stop once a page reaches what an earlier completed scan covered. A
    completed scan describes API traversals, not all historical events or a
    safe timestamp for acknowledging notifications. Replays preserve event
    identities; this function neither runs Phi nor marks anything seen.
    """
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    receipt = {
        "id": f"scan-{uuid4()}",
        "kind": "encounter_scan",
        "status": "started",
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": "",
        "pages_captured": 0,
        "deliveries_captured": 0,
        "max_pages": max_pages,
        "covered_until": "",
        "error": "",
    }

    async def save() -> None:
        await asyncio.to_thread(
            storage.namespace(namespace).write, upsert_rows=[dict(receipt)]
        )

    receipt["covered_until"] = await covered_until(storage, namespace)
    await save()
    try:
        async for page in notification_pages(client, max_pages=max_pages):
            captured_at = datetime.now(UTC)
            await append_encounters(
                storage,
                namespace,
                [notification_encounter(n, captured_at) for n in page.notifications],
            )
            receipt["pages_captured"] += 1
            receipt["deliveries_captured"] += len(page.notifications)
            await save()
            if receipt["covered_until"] and any(
                indexed_time(n.indexed_at) < receipt["covered_until"]
                for n in page.notifications
            ):
                break
    except asyncio.CancelledError:
        # The durable started receipt deliberately remains incomplete. Shutdown
        # may prevent further writes; it must never manufacture completion.
        raise
    except Exception as exc:
        receipt.update(
            status="failed",
            finished_at=datetime.now(UTC).isoformat(),
            error=str(exc),
        )
        await save()
        raise
    receipt.update(status="completed", finished_at=datetime.now(UTC).isoformat())
    await save()
    return receipt
