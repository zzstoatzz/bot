"""Compact entity pages for Coral's unpaginated graph endpoint."""

import json
from datetime import UTC, datetime

ENTITY_FIELDS = (
    "id",
    "text",
    "label",
    "rate",
    "count",
    "trend",
    "surprise",
    "baseline",
    "cluster",
    "cluster_score",
    "largest",
)


def entity_page(payload: dict, query: str, limit: int, offset: int) -> str:
    """Project complete entity summaries; never slice serialized JSON."""
    entities = payload.get("entities")
    if not isinstance(entities, list) or any(
        not isinstance(entity, dict) or not isinstance(entity.get("text"), str)
        for entity in entities
    ):
        raise ValueError("Coral response has no valid entities list")
    query = query.strip().casefold()
    matches = sorted(
        (entity for entity in entities if query in entity["text"].casefold()),
        key=lambda entity: (entity["text"].casefold(), str(entity.get("id", ""))),
    )
    page = []
    for entity in matches[offset : offset + limit]:
        item = {key: entity[key] for key in ENTITY_FIELDS if key in entity}
        item["edge_count"] = len(entity.get("edges", []))
        page.append(item)
    return json.dumps(
        {
            "fetched_at": datetime.now(UTC).isoformat(),
            "total_entities": len(entities),
            "matching_entities": len(matches),
            "query": query,
            "order": "entity name, then id",
            "offset": offset,
            "returned": len(page),
            "next_offset": offset + len(page)
            if offset + len(page) < len(matches)
            else None,
            "view": "Complete entity summaries; edge lists and visualization coordinates omitted. "
            "Each call reads the live graph; pages can change between calls.",
            "entities": page,
        },
        ensure_ascii=False,
    )
