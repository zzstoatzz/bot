"""Cross-person text retrieval and exact reads of captured source events."""

import asyncio
import logging
from typing import Literal, TypedDict

from turbopuffer import NotFoundError, Turbopuffer

logger = logging.getLogger(__name__)


class EncounterSearch(TypedDict):
    status: Literal["ok", "not_initialized", "unavailable"]
    rows: list[dict]
    has_more: bool


async def search_encounters(
    client: Turbopuffer,
    namespace: str,
    query: str,
    *,
    limit: int = 8,
    actor_did: str | None = None,
) -> EncounterSearch:
    """One namespace query across captured people; no person-store fanout.

    Text matching covers captured notification text only. It does not search
    uncaptured history, old extracted memories, or infer a decision from silence.
    """
    if not query.strip() or not 1 <= limit <= 100:
        raise ValueError("a nonempty query and a limit from 1 to 100 are required")
    filters: list = ["kind", "Eq", "encounter"]
    if actor_did:
        filters = ["And", [filters, ["actor_did", "Eq", actor_did]]]
    try:
        response = await asyncio.to_thread(
            client.namespace(namespace).query,
            rank_by=("content", "BM25", query),
            filters=filters,
            top_k=limit + 1,
            include_attributes=True,
        )
        rows = response.rows or []
        return EncounterSearch(
            status="ok",
            rows=[r.model_dump() for r in rows[:limit]],
            has_more=len(rows) > limit,
        )
    except NotFoundError:
        return EncounterSearch(status="not_initialized", rows=[], has_more=False)
    except Exception:
        logger.exception("encounter search unavailable")
        return EncounterSearch(status="unavailable", rows=[], has_more=False)


async def read_encounter(
    client: Turbopuffer, namespace: str, event_id: str
) -> EncounterSearch:
    """Recover the stored source version by the ID printed in search/context."""
    if not event_id:
        raise ValueError("an encounter ID is required")
    try:
        response = await asyncio.to_thread(
            client.namespace(namespace).query,
            rank_by=("id", "asc"),
            filters=["And", [["kind", "Eq", "encounter"], ["id", "Eq", event_id]]],
            top_k=1,
            include_attributes=True,
        )
        return EncounterSearch(
            status="ok",
            rows=[r.model_dump() for r in response.rows or []],
            has_more=False,
        )
    except NotFoundError:
        return EncounterSearch(status="not_initialized", rows=[], has_more=False)
    except Exception:
        logger.exception("encounter source read unavailable")
        return EncounterSearch(status="unavailable", rows=[], has_more=False)


async def read_encounter_activity(
    client: Turbopuffer, namespace: str, event_id: str, *, limit: int = 12
) -> EncounterSearch:
    """Recent run/request receipts referencing an event; actions live in traces."""
    if not event_id or not 1 <= limit <= 100:
        raise ValueError("an encounter ID and a limit from 1 to 100 are required")
    try:
        response = await asyncio.to_thread(
            client.namespace(namespace).query,
            rank_by=("recorded_at", "desc"),
            filters=["event_ids", "Contains", event_id],
            top_k=limit + 1,
            include_attributes=True,
        )
        rows = response.rows or []
        return EncounterSearch(
            status="ok",
            rows=[r.model_dump() for r in rows[:limit]],
            has_more=len(rows) > limit,
        )
    except NotFoundError:
        return EncounterSearch(status="not_initialized", rows=[], has_more=False)
    except Exception:
        logger.exception("encounter activity read unavailable")
        return EncounterSearch(status="unavailable", rows=[], has_more=False)
