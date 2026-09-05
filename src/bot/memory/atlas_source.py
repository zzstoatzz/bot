"""Resolve a derived atlas point to its existing private memory row."""

import asyncio
import logging

from turbopuffer import Turbopuffer

logger = logging.getLogger("bot.memory.atlas_source")


async def read_atlas_source(client: Turbopuffer, point: dict) -> str:
    """Read only an exact Phi memory reference; never infer an ID from a label."""
    refs = point.get("refs") or {}
    namespace = refs.get("tpuf_namespace")
    row_id = refs.get("tpuf_id")
    if not isinstance(namespace, str) or not isinstance(row_id, str) or not row_id:
        return "Stored source unavailable: atlas point has no exact memory reference."
    if namespace != "phi-episodic" and not namespace.startswith("phi-users-"):
        return (
            "Stored source unavailable: reference is outside Phi's memory namespaces."
        )

    try:
        response = await asyncio.to_thread(
            client.namespace(namespace).query,
            rank_by=("id", "asc"),
            filters=("id", "Eq", row_id),
            top_k=1,
            include_attributes=True,
        )
    except Exception:
        logger.exception("Atlas source lookup failed for %s/%s", namespace, row_id)
        return "Stored source lookup failed; this does not establish that the row is absent."

    rows = response.rows or []
    if not rows:
        return "Stored source not found at the atlas reference; the projection may be stale."
    row = rows[0]
    if str(row.id) != row_id:
        return (
            "Stored source unavailable: returned row did not match the atlas reference."
        )
    kind = getattr(row, "kind", None) or "unspecified (legacy row)"
    created = getattr(row, "created_at", None) or "unavailable"
    status = getattr(row, "status", None) or "unspecified (legacy row)"
    lines = [
        "Stored memory source (current row, not the atlas snapshot):",
        f"namespace: {namespace}",
        f"row_id: {row_id}",
        f"kind: {kind}",
        f"created_at: {created}",
        f"status: {status}",
        "content:",
        getattr(row, "content", None) or "(no stored content)",
    ]
    sources = getattr(row, "source_uris", None) or []
    lines.append("source_uris:")
    lines.extend(f"- {uri}" for uri in sources)
    if not sources:
        lines.append("(none stored)")
    return "\n".join(lines)
