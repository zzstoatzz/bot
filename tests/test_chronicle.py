"""The chronicle tiles all recorded history and stays bounded as it grows."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

from turbopuffer import Turbopuffer

from bot.memory import chronicle
from bot.memory.chronicle import (
    FANOUT,
    FLUSH_ITEMS,
    Flush,
    Merge,
    compact,
    correct_entry,
    next_operation,
    render_chronicle,
)

T0 = datetime(2026, 3, 24, tzinfo=UTC)


class FakeNamespace:
    """The query/write subset chronicle uses, with turbopuffer's semantics."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows = {r["id"]: dict(r) for r in rows or []}
        self.writes = 0

    def query(self, *, rank_by, top_k, filters=None, include_attributes=None):
        attr, _ = rank_by
        rows = list(self.rows.values())
        if isinstance(filters, tuple):
            key, op, value = filters
            if op == "Eq":
                rows = [r for r in rows if r.get(key) == value]
            elif op == "Gt":
                rows = [r for r in rows if r.get(key, "") > value]
        rows.sort(key=lambda r: r[attr])
        return SimpleNamespace(
            rows=[SimpleNamespace(model_dump=lambda r=r: dict(r)) for r in rows[:top_k]]
        )

    def write(self, *, schema, upsert_rows=None, patch_rows=None):
        self.writes += 1
        for row in upsert_rows if isinstance(upsert_rows, list) else []:
            self.rows[row["id"]] = dict(row)
        for patch in patch_rows if isinstance(patch_rows, list) else []:
            self.rows[patch["id"]].update(patch)


class FakeClient:
    def __init__(self, records: list[dict]):
        self.spaces = {
            chronicle.EPISODIC_NAMESPACE: FakeNamespace(records),
            chronicle.CHRONICLE_NAMESPACE: FakeNamespace(),
        }

    def namespace(self, name: str) -> FakeNamespace:
        return self.spaces[name]

    @property
    def entries(self) -> list[dict]:
        return list(self.spaces[chronicle.CHRONICLE_NAMESPACE].rows.values())


def tp(client: FakeClient) -> Turbopuffer:
    return cast(Turbopuffer, client)


def records(n: int, status=lambda i: "active") -> list[dict]:
    return [
        {
            "id": f"ep{i:05d}",
            "content": f"event {i}",
            "source": "run:cycle",
            "status": status(i),
            "created_at": (T0 + timedelta(hours=i)).isoformat(),
        }
        for i in range(n)
    ]


async def echo(op):
    return f"level {op.level if isinstance(op, Merge) else 1}"


async def test_history_is_tiled_without_gaps_and_bounded_per_level():
    raw = records(2000)
    client = FakeClient(raw)
    now = T0 + timedelta(hours=2000) + chronicle.FLUSH_AGE
    while await compact(tp(client), now=now, summarize=echo):
        pass

    active = sorted(
        (e for e in client.entries if e["status"] == "active"), key=lambda e: e["start"]
    )
    assert active[0]["start"] == raw[0]["created_at"]
    assert sum(e["items"] for e in active) == len(raw)
    for older, newer in zip(active, active[1:]):
        assert older["end"] < newer["start"]
        assert older["level"] >= newer["level"]  # coarser with age
    per_level = Counter(e["level"] for e in active)
    assert max(per_level.values()) <= FANOUT
    assert len(active) <= FANOUT * len(per_level)
    # merged inputs remain, each pointing at the entry that replaced it
    merged = [e for e in client.entries if e["status"] == "merged"]
    by_id = {e["id"]: e for e in client.entries}
    assert merged and all(e["id"] in by_id[e["merged_into"]]["inputs"] for e in merged)


async def test_records_wait_for_a_full_flush_until_they_age():
    raw = records(FLUSH_ITEMS - 1)
    young = T0 + timedelta(hours=FLUSH_ITEMS)
    assert next_operation([], raw, young) is None
    op = next_operation([], raw, T0 + chronicle.FLUSH_AGE)
    assert isinstance(op, Flush) and len(op.records) == FLUSH_ITEMS - 1


async def test_retired_records_are_left_out_and_superseded_are_marked():
    raw = records(
        FLUSH_ITEMS + 2,
        status=lambda i: {0: "retired", 1: "superseded"}.get(i, "active"),
    )
    client = FakeClient(raw)
    prompts = []

    async def capture(op):
        prompts.append(chronicle.operation_prompt(op))
        return "entry"

    assert await compact(
        tp(client), now=T0 + timedelta(hours=40), budget=1, summarize=capture
    )
    assert "event 0\n" not in prompts[0] + "\n"
    assert "[superseded by a later version]\nevent 1" in prompts[0]
    (entry,) = client.entries
    assert "ep00000" not in entry["inputs"] and entry["items"] == FLUSH_ITEMS


async def test_a_correction_renders_and_overrides_the_entry_when_merged():
    client = FakeClient(records(FLUSH_ITEMS * (FANOUT + 1)))
    now = T0 + timedelta(days=30)
    assert await compact(tp(client), now=now, budget=FANOUT, summarize=echo) == FANOUT
    first = min(client.entries, key=lambda e: e["start"])
    result = await correct_entry(tp(client), first["id"], "she lost that season", now)
    assert result["status"] == "ok"
    assert "correction 2026-04-23: she lost that season" in render_chronicle(
        client.entries
    )

    prompts = []

    async def capture(op):
        prompts.append(chronicle.operation_prompt(op))
        return "merged"

    while await compact(tp(client), now=now, budget=1, summarize=capture):
        pass
    assert any(
        "correction (overrides the entry above): 2026-04-23: she lost that season" in p
        for p in prompts
    )
    stale = await correct_entry(tp(client), first["id"], "again", now)
    assert stale["status"] == "merged" and stale["merged_into"]


async def test_an_empty_summary_writes_nothing():
    client = FakeClient(records(FLUSH_ITEMS))

    async def empty(op):
        return ""

    try:
        await compact(tp(client), now=T0 + timedelta(days=3), summarize=empty)
    except ValueError:
        pass
    assert client.entries == []
