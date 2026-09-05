"""Exact, read-only access to a stored episodic version."""

import asyncio
import logging

from turbopuffer import NotFoundError

logger = logging.getLogger(__name__)


async def read_note(namespace, note_id: str) -> dict:
    """Return one version, including superseded records, without synthesis."""
    if not note_id.strip():
        return {"status": "invalid_id", "note": None}
    try:
        result = await asyncio.to_thread(
            namespace.query,
            rank_by=("id", "asc"),
            filters=["id", "Eq", note_id],
            top_k=1,
            include_attributes=True,
        )
    except NotFoundError:
        return {"status": "namespace_missing", "note": None}
    except Exception:
        logger.exception("episodic version read failed")
        return {"status": "unavailable", "note": None}
    if not result.rows:
        return {"status": "not_found", "note": None}
    row = result.rows[0]
    sources = list(getattr(row, "source_uris", []) or [])
    supplied = list(getattr(row, "submitted_source_uris", []) or [])
    provenance_known = getattr(row, "source_provenance_version", None) == 1
    return {
        "status": "ok",
        "note": {
            "id": row.id,
            "content": row.content,
            "created_at": getattr(row, "created_at", None),
            "source": getattr(row, "source", None),
            "status": getattr(row, "status", None),
            "tags": list(getattr(row, "tags", []) or []),
            "source_uris": sources,
            "source_provenance": {
                "status": "recorded" if provenance_known else "unknown_legacy",
                "submitted": supplied if provenance_known else None,
                "inherited": [uri for uri in sources if uri not in supplied]
                if provenance_known else None,
                "verification": "not_performed_by_memory_storage",
            },
            "supersedes": getattr(row, "supersedes", None),
        },
    }
