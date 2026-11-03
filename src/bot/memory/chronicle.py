"""A standing distillation of everything phi has recorded, finest where newest.

The episodic namespace is the raw stream. Once `FLUSH_ITEMS` records have
accumulated past the newest entry, or the oldest of them has waited
`FLUSH_AGE`, they are summarized into one level-1 entry. A level holding
more than `FANOUT` entries merges its oldest `FANOUT` into one entry at the
next level. Spans grow geometrically with age, so the whole history fits a
few thousand tokens while the recent past keeps its detail.

Entries are never rewritten. A merge writes the new entry and marks its
inputs merged in the same write, so the stack switches over in one step and
the inputs stay readable. Corrections attach to an entry and override its
text in every later merge. The summarizer sees only its inputs: no goals,
no ambient context, nothing that could corroborate a claim the records
don't make.
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic_ai import Agent
from turbopuffer import NotFoundError, Turbopuffer, omit
from turbopuffer.types import AttributeSchemaConfigParam

from bot.config import settings

logger = logging.getLogger("bot.memory.chronicle")

CHRONICLE_NAMESPACE = "phi-chronicle"
EPISODIC_NAMESPACE = "phi-episodic"
FLUSH_ITEMS = 30
FLUSH_AGE = timedelta(days=2)
FANOUT = 4
ITEM_CHARS = 1500
RENDER_TTL_S = 300

CHRONICLE_SCHEMA: dict[str, str | AttributeSchemaConfigParam] = {
    "level": {"type": "uint", "filterable": True},
    "status": {"type": "string", "filterable": True},  # active, merged
    "start": {"type": "string", "filterable": True},
    "end": {"type": "string"},
    "text": {"type": "string"},
    "inputs": {"type": "[]string"},
    "items": {"type": "uint"},
    "corrections": {"type": "[]string"},
    "created_at": {"type": "string"},
    "merged_into": {"type": "string"},
}


def _words(level: int) -> int:
    return {1: 120, 2: 160}.get(level, 200)


@dataclass
class Flush:
    records: list[dict]


@dataclass
class Merge:
    level: int
    entries: list[dict]


def _parse(stamp: str) -> datetime:
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def next_operation(
    stack: list[dict], raw: list[dict], now: datetime
) -> Flush | Merge | None:
    """Merges first, so a flush never lands on an overfull level."""
    levels: dict[int, list[dict]] = defaultdict(list)
    for entry in sorted(stack, key=lambda e: e["start"]):
        levels[entry["level"]].append(entry)
    for level in sorted(levels):
        if len(levels[level]) > FANOUT:
            return Merge(level + 1, levels[level][:FANOUT])
    if len(raw) >= FLUSH_ITEMS or (
        raw and now - _parse(raw[0]["created_at"]) >= FLUSH_AGE
    ):
        return Flush(raw[:FLUSH_ITEMS])
    return None


def build_entry(op: Flush | Merge, text: str, now: datetime) -> dict:
    if isinstance(op, Flush):
        level, start, end = 1, op.records[0]["created_at"], op.records[-1]["created_at"]
        inputs, items = [r["id"] for r in op.records], len(op.records)
    else:
        level, start, end = op.level, op.entries[0]["start"], op.entries[-1]["end"]
        inputs = [e["id"] for e in op.entries]
        items = sum(e["items"] for e in op.entries)
    identity = f"{level}|{start}|{end}".encode()
    return {
        "id": hashlib.sha256(identity).hexdigest()[:16],
        "level": level,
        "status": "active",
        "start": start,
        "end": end,
        "text": text,
        "inputs": inputs,
        "items": items,
        "corrections": [],
        "created_at": now.isoformat(),
        "merged_into": "",
    }


def _clip(text: str, cap: int) -> str:
    return text if len(text) <= cap else text[: cap - 1] + "…"


def operation_prompt(op: Flush | Merge) -> str:
    if isinstance(op, Flush):
        lines = [
            f"Write a level-1 entry, at most {_words(1)} words, from these "
            f"{len(op.records)} records (oldest first). Keep the concrete "
            "events: what she did, with whom, what changed, what she concluded, "
            "and what was still open at the end."
        ]
        for record in op.records:
            state = record.get("status") or "active"
            marker = " [superseded by a later version]" if state == "superseded" else ""
            lines.append(
                f"\n[{record['created_at'][:16]}] {record.get('source', '')}{marker}\n"
                + _clip(record.get("content") or "", ITEM_CHARS)
            )
        return "\n".join(lines)
    lines = [
        f"Write a level-{op.level} entry, at most {_words(op.level)} words, "
        f"merging these {len(op.entries)} consecutive entries (oldest first) "
        "into one account of the whole span. Keep what persisted, what changed "
        "direction, and what was settled or still open at the end; drop "
        "one-off detail."
    ]
    for entry in op.entries:
        lines.append(
            f"\n[{entry['start'][:10]} to {entry['end'][:10]}]\n{entry['text']}"
        )
        lines.extend(
            f"correction (overrides the entry above): {c}"
            for c in entry.get("corrections") or []
        )
    return "\n".join(lines)


_summarizer: Agent[None, str] | None = None


def _get_summarizer() -> Agent[None, str]:
    global _summarizer
    if _summarizer is None:
        _summarizer = Agent[None, str](
            name="phi-chronicle",
            model=settings.chronicle_model,
            system_prompt=(
                "You write one entry of phi's chronicle: a dated account of a "
                "span of her history, compiled from her own records. phi is a "
                "Bluesky bot; she reads the chronicle as background in every "
                "run, so it has to be accurate and plain.\n\n"
                "- The records are phi's own accounts: run summaries and notes. "
                "They report what she did and believed, which is not always "
                "what was true. Keep that distinction where it matters.\n"
                "- A later record overrides an earlier one. Superseded records "
                "are history. A correction overrides the text it corrects.\n"
                "- Say only what the inputs support. No speculation about what "
                "comes next, no advice, no assessment of how she is doing.\n"
                "- Third person ('phi' or 'she'), past tense, concrete names, "
                "handles and numbers. No rhetoric, no em dashes.\n"
                "- Output only the entry text."
            ),
            output_type=str,
        )
    return _summarizer


async def summarize(op: Flush | Merge) -> str:
    result = await _get_summarizer().run(operation_prompt(op))
    return (result.output or "").strip()


def _rows(response) -> list[dict]:
    return [row.model_dump() for row in (response.rows or [])]


async def read_stack(client: Turbopuffer) -> list[dict]:
    try:
        response = await asyncio.to_thread(
            client.namespace(CHRONICLE_NAMESPACE).query,
            rank_by=("start", "asc"),
            filters=("status", "Eq", "active"),
            top_k=1000,
            include_attributes=True,
        )
    except NotFoundError:
        return []
    return _rows(response)


async def read_raw(client: Turbopuffer, after: str, limit: int) -> list[dict]:
    """Up to `limit` episodic records past `after`, oldest first, retired ones left out."""
    kept: list[dict] = []
    while len(kept) < limit:
        response = await asyncio.to_thread(
            client.namespace(EPISODIC_NAMESPACE).query,
            rank_by=("created_at", "asc"),
            filters=("created_at", "Gt", after) if after else omit,
            top_k=limit,
            include_attributes=["content", "source", "status", "created_at"],
        )
        page = _rows(response)
        kept += [r for r in page if r.get("status") != "retired"]
        if len(page) < limit:
            break
        after = page[-1]["created_at"]
    return kept[:limit]


async def _write(client: Turbopuffer, entry: dict, merged: list[str]) -> None:
    await asyncio.to_thread(
        client.namespace(CHRONICLE_NAMESPACE).write,
        upsert_rows=[entry],
        patch_rows=[
            {"id": i, "status": "merged", "merged_into": entry["id"]} for i in merged
        ]
        or omit,
        schema=CHRONICLE_SCHEMA,
    )
    invalidate()


async def compact(
    client: Turbopuffer,
    *,
    budget: int = 20,
    now: datetime | None = None,
    summarize=summarize,
) -> int:
    """Apply due flushes and merges, at most `budget` of them; returns how many."""
    done = 0
    while done < budget:
        moment = now or datetime.now(UTC)
        stack = await read_stack(client)
        cursor = max((e["end"] for e in stack), default="")
        op = next_operation(stack, await read_raw(client, cursor, FLUSH_ITEMS), moment)
        if op is None:
            break
        text = await summarize(op)
        if not text:
            raise ValueError("chronicle summarizer returned no text")
        entry = build_entry(op, text, moment)
        merged = [e["id"] for e in op.entries] if isinstance(op, Merge) else []
        await _write(client, entry, merged)
        logger.info(
            f"chronicle: level {entry['level']} {entry['start'][:10]}"
            f"..{entry['end'][:10]} from {len(entry['inputs'])} inputs"
        )
        done += 1
    return done


async def correct_entry(
    client: Turbopuffer, entry_id: str, correction: str, now: datetime
) -> dict:
    try:
        response = await asyncio.to_thread(
            client.namespace(CHRONICLE_NAMESPACE).query,
            rank_by=("id", "asc"),
            filters=("id", "Eq", entry_id),
            top_k=1,
            include_attributes=["status", "merged_into", "corrections"],
        )
    except NotFoundError:
        return {"status": "not_found"}
    rows = _rows(response)
    if not rows:
        return {"status": "not_found"}
    entry = rows[0]
    if entry.get("status") == "merged":
        return {"status": "merged", "merged_into": entry.get("merged_into")}
    corrections = [*(entry.get("corrections") or []), f"{now.date()}: {correction}"]
    await asyncio.to_thread(
        client.namespace(CHRONICLE_NAMESPACE).write,
        patch_rows=[{"id": entry_id, "corrections": corrections}],
        schema=CHRONICLE_SCHEMA,
    )
    invalidate()
    return {"status": "ok", "corrections": corrections}


def _span(entry: dict) -> str:
    start, end = entry["start"][:10], entry["end"][:10]
    return start if start == end else f"{start} to {end}"


def render_chronicle(stack: list[dict]) -> str:
    if not stack:
        return ""
    stack = sorted(stack, key=lambda e: e["start"])
    lines = [
        f"[CHRONICLE — your history from {stack[0]['start'][:10]} through "
        f"{stack[-1]['end'][:10]}, oldest first. A separate summarizer compiles "
        "it from your episodic records, folding older spans into coarser "
        "entries; it is your own account, not verified fact, and the newest "
        "records are not in it yet. Background for orientation, not a task "
        "list. correct_chronicle attaches a correction to an entry that is "
        "wrong.]"
    ]
    for entry in stack:
        lines.append(f"- {_span(entry)} (entry {entry['id']}): {entry['text']}")
        lines.extend(f"  correction {c}" for c in entry.get("corrections") or [])
    return "\n".join(lines)


_rendered: tuple[float, str] | None = None


def invalidate() -> None:
    global _rendered
    _rendered = None


async def get_chronicle_block(client: Turbopuffer) -> str:
    global _rendered
    if _rendered and time.monotonic() - _rendered[0] < RENDER_TTL_S:
        return _rendered[1]
    try:
        block = render_chronicle(await read_stack(client))
    except Exception as e:
        logger.warning(f"chronicle read failed: {e}")
        return "[CHRONICLE] unavailable this run; your long history is not shown."
    _rendered = (time.monotonic(), block)
    return block
