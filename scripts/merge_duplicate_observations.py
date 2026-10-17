"""One-off: reconcile active observations that were never compared.

sandbox/observation_neighbor_audit.py (2026-10-03) found 284 pairs of active
observations within cosine distance 0.25. Nearly all came from the likes
phase of my-prefect-server's compact flow, which wrote without looking at
vector neighbours. This runs phi's own reconciler over each such row, newest
first, against its close active neighbours.

The plan is written first and applied second, so what was reviewed is what
gets written. Nothing is deleted: rows are marked superseded, and a merged
row links back through `supersedes`.

Run from the bot/ directory:

    uv run python scripts/merge_duplicate_observations.py           # write the plan
    uv run python scripts/merge_duplicate_observations.py --apply   # apply the saved plan
    uv run python scripts/merge_duplicate_observations.py --restore-status
"""

import argparse
import asyncio
import json
import os
import time
from collections import Counter
from pathlib import Path

from turbopuffer.types.custom import Filter

from bot.config import settings
from bot.memory.extraction import (
    Observation,
    get_reconciliation_agent,
    reconciliation_prompt,
    reconciliation_targets,
)
from bot.memory.namespace_memory import NamespaceMemory

# rows are stamped with datetime.now(); the bot runs in UTC, a laptop does not.
os.environ["TZ"] = "UTC"
time.tzset()

AUDIT = Path("sandbox/observation-neighbor-audit.json")
PLAN = Path("sandbox/observation-merge-plan.json")
MAX_DISTANCE = 0.25
ACTIVE: Filter = (
    "And",
    [("kind", "Eq", "observation"), ("status", "NotEq", "superseded")],
)


def _row(row) -> dict:
    return {
        "id": row.id,
        "content": row.content,
        "tags": list(getattr(row, "tags", []) or []),
        "source_uris": list(getattr(row, "source_uris", []) or []),
        "created_at": getattr(row, "created_at", "") or "",
    }


async def plan() -> None:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key or "")
    mem = NamespaceMemory(api_key=settings.turbopuffer_api_key)
    by_namespace: dict[str, set[str]] = {}
    for pair in json.loads(AUDIT.read_text()):
        by_namespace.setdefault(pair["namespace"], set()).update(
            (pair["id"], pair["neighbour_id"])
        )

    steps: list[dict] = []
    for name, ids in sorted(by_namespace.items()):
        ns = mem.client.namespace(name)
        response = ns.query(
            rank_by=("created_at", "desc"),
            top_k=1000,
            filters=ACTIVE,
            include_attributes=True,
        )
        candidates = [r for r in response.rows or [] if r.id in ids]
        retired: set[str] = set()
        for row in sorted(
            candidates, key=lambda r: _row(r)["created_at"], reverse=True
        ):
            if row.id in retired or not isinstance(row.vector, list):
                continue
            near = ns.query(
                rank_by=("vector", "ANN", row.vector),
                top_k=8,
                filters=ACTIVE,
                include_attributes=True,
            )
            neighbours = [
                _row(n)
                for n in near.rows or []
                if n.id != row.id and n.id not in retired and n["$dist"] <= MAX_DISTANCE
            ][:3]
            if not neighbours:
                continue
            new = _row(row)
            result = await get_reconciliation_agent().run(
                reconciliation_prompt(neighbours, new["content"], new["tags"])
            )
            decision = result.output.decision
            action = decision.action.upper()
            targets = reconciliation_targets(decision, neighbours)
            step = {
                "namespace": name,
                "action": action,
                "reason": decision.reason,
                "row": new,
                "neighbours": neighbours,
                "supersede": [],
                "write": None,
            }
            if action == "NOOP":
                step["supersede"] = [new["id"]]
            elif action == "DELETE":
                step["supersede"] = [t["id"] for t in targets]
            elif action == "UPDATE":
                step["supersede"] = [new["id"], *(t["id"] for t in targets)]
                step["write"] = {
                    "content": decision.new_content or new["content"],
                    "tags": (decision.new_tags or new["tags"])[:3],
                    "supersedes": new["id"],
                    "source_uris": list(
                        dict.fromkeys(
                            new["source_uris"]
                            + [u for t in targets for u in t["source_uris"]]
                        )
                    ),
                }
            retired.update(step["supersede"])
            steps.append(step)
        print(f"{name}: {len(candidates)} rows in close pairs")

    PLAN.write_text(json.dumps(steps, indent=2))
    actions = Counter(s["action"] for s in steps)
    print(f"\n{len(steps)} decisions: {dict(actions)}")
    print(f"rows to supersede: {sum(len(s['supersede']) for s in steps)}")
    print(f"merged rows to write: {sum(1 for s in steps if s['write'])}")
    print(f"plan: {PLAN}")


async def apply() -> None:
    mem = NamespaceMemory(api_key=settings.turbopuffer_api_key)
    steps = [s for s in json.loads(PLAN.read_text()) if s["supersede"]]
    for step in steps:
        handle = step["namespace"].removeprefix("phi-users-")
        if write := step["write"]:
            await mem._write_observation(
                handle,
                Observation(content=write["content"], tags=write["tags"]),
                await mem._get_embedding(write["content"]),
                supersedes=write["supersedes"],
                source_uris_override=write["source_uris"],
            )
        mem.client.namespace(step["namespace"]).write(
            patch_rows=[{"id": i, "status": "superseded"} for i in step["supersede"]]
        )
    print(f"applied {len(steps)} steps")


def restore() -> None:
    """Re-mark rows the applied plan superseded that have since lost `status`.

    my-prefect-server's tag maintenance upserted whole rows until cb03d28,
    which dropped the field and made them active again.
    """
    mem = NamespaceMemory(api_key=settings.turbopuffer_api_key)
    wanted: dict[str, set[str]] = {}
    for step in json.loads(PLAN.read_text()):
        wanted.setdefault(step["namespace"], set()).update(step["supersede"])
    restored = 0
    for name, ids in sorted(wanted.items()):
        ns = mem.client.namespace(name)
        response = ns.query(
            rank_by=("created_at", "desc"),
            top_k=1000,
            filters=("kind", "Eq", "observation"),
            include_attributes=["status"],
        )
        lost = [
            row.id
            for row in response.rows or []
            if row.id in ids and getattr(row, "status", None) is None
        ]
        if lost:
            ns.write(patch_rows=[{"id": i, "status": "superseded"} for i in lost])
            restored += len(lost)
    print(f"restored superseded status on {restored} rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--restore-status", action="store_true")
    args = parser.parse_args()
    if args.restore_status:
        restore()
    else:
        asyncio.run(apply() if args.apply else plan())
