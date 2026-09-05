"""Recover visible notification history without dispatching public actions."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from turbopuffer import Turbopuffer

from bot.core.atproto_client import BotClient
from bot.memory.encounters import append_encounters, notification_encounter
from bot.services.notification_history import notification_pages


async def recover_encounters(
    client: BotClient,
    storage: Turbopuffer,
    namespace: str,
    *,
    max_pages: int = 100,
) -> dict:
    """Store each page before advancing and record the traversal's outcome.

    Always start from the newest visible page, independently of UI read state.
    A completed scan describes one API traversal, not all historical events or
    a safe timestamp for acknowledging notifications. Replays preserve event
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
        "error": "",
    }

    async def save() -> None:
        await asyncio.to_thread(
            storage.namespace(namespace).write, upsert_rows=[dict(receipt)]
        )

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
