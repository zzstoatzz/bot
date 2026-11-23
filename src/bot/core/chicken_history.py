"""Local copy of settled Top Chicken rounds, for backtesting phi's policies.

Each settled round is fetched once and never again: its result (winner, void
or settled), the 25 published standings, and each standing's price/likes chart.
A round that is not settled yet is skipped and picked up on a later sync, so
after the first backfill a sync costs one new round (~10MB of charts).

`/api/results/{round}` publishes only the final top 25 by likes, while a live
round carries ~150 contenders. A policy replayed here can only choose among
names that finished in that top 25, which flatters it; `chicken_backtest`
limits choices to the current top K and names this bias in every report.
"""

import asyncio
import json
import logging
import sqlite3
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger("bot.chicken_history")

API = "https://topchicken.cee.wtf/api"
DB_PATH = Path("/data/chicken_history.sqlite3")
FIRST_ROUND = date(2026, 7, 1)
REQUEST_SPACING_S = 1.5

SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    window_start INTEGER NOT NULL,
    lock_at INTEGER NOT NULL,
    winner_did TEXT
);
CREATE TABLE IF NOT EXISTS charts (
    round TEXT NOT NULL,
    did TEXT NOT NULL,
    handle TEXT NOT NULL,
    final_likes INTEGER NOT NULL,
    ticks BLOB NOT NULL,
    PRIMARY KEY (round, did)
);
"""


@dataclass(frozen=True)
class Chart:
    did: str
    handle: str
    final_likes: int
    ticks: list[tuple[int, float, int, float]]  # ts, p, likes, velocity/hr


@dataclass(frozen=True)
class Round:
    id: str
    status: str
    window_start: int
    lock_at: int
    winner_did: str | None
    charts: list[Chart]


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def _pack(ticks: list[list]) -> bytes:
    rows = [
        [int(t[0]), round(float(t[1]), 6), int(t[2]), round(float(t[3]), 2)]
        for t in ticks
    ]
    return zlib.compress(json.dumps(rows, separators=(",", ":")).encode(), 9)


def _unpack(blob: bytes) -> list[tuple[int, float, int, float]]:
    return [tuple(r) for r in json.loads(zlib.decompress(blob))]


async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """GET at a pace a small hobby site can take, backing off when it says 429."""
    for attempt in range(6):
        await asyncio.sleep(REQUEST_SPACING_S)
        r = await client.get(url)
        if r.status_code != 429:
            return r
        await asyncio.sleep(30 * 2**attempt)
    r.raise_for_status()
    return r


async def _fetch_round(
    client: httpx.AsyncClient, round_id: str
) -> tuple[dict, list[dict]] | None:
    """A settled or void round's result and its charts; None until it settles."""
    r = await _get(client, f"{API}/results/{round_id}")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    meta = data.get("round") or {}
    if meta.get("status") not in ("settled", "void"):
        return None
    charts = []
    for s in data.get("standings") or []:
        c = await _get(client, f"{API}/chart/{round_id}/{s['did']}")
        c.raise_for_status()
        charts.append({**s, "ticks": c.json().get("ticks") or []})
    return meta, charts


async def sync(
    path: Path = DB_PATH, today: date | None = None, limit: int | None = None
) -> int:
    """Fetch settled rounds not stored yet; return how many were added.

    With `limit`, only rounds after the newest stored one are tried, at most
    `limit` of them, and an empty store fetches nothing: the full backfill is
    a separate one-time run, never a side effect of a tool call.
    """
    db = connect(path)
    have = {row[0] for row in db.execute("SELECT id FROM rounds")}
    last = (today or datetime.now(UTC).date()) - timedelta(days=1)
    wanted = []
    d = FIRST_ROUND
    while d <= last:
        if d.isoformat() not in have:
            wanted.append(d.isoformat())
        d += timedelta(days=1)
    if limit is not None:
        newest = max(have, default=None)
        wanted = [r for r in wanted if newest and r > newest][:limit]
    added = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        for round_id in wanted:
            fetched = await _fetch_round(client, round_id)
            if fetched is None:
                continue
            meta, charts = fetched
            with db:
                db.execute(
                    "INSERT INTO rounds VALUES (?, ?, ?, ?, ?)",
                    (
                        round_id,
                        meta["status"],
                        int(meta["window_start"]),
                        int(meta["lock_at"]),
                        meta.get("winner_did"),
                    ),
                )
                db.executemany(
                    "INSERT INTO charts VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            round_id,
                            c["did"],
                            c.get("handle") or c["did"],
                            int(c.get("likes") or 0),
                            _pack(c["ticks"]),
                        )
                        for c in charts
                    ],
                )
            added += 1
            logger.info("chicken history: stored %s (%d charts)", round_id, len(charts))
    db.close()
    return added


def load(path: Path = DB_PATH) -> Iterator[Round]:
    """Every stored round, oldest first, one at a time to keep memory to a round."""
    db = connect(path)
    try:
        meta = db.execute("SELECT * FROM rounds ORDER BY id").fetchall()
        for rid, status, ws, lock, winner in meta:
            charts = [
                Chart(did, handle, likes, _unpack(blob))
                for did, handle, likes, blob in db.execute(
                    "SELECT did, handle, final_likes, ticks FROM charts WHERE round = ?",
                    (rid,),
                )
            ]
            yield Round(rid, status, ws, lock, winner, charts)
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    print(f"added {asyncio.run(sync(target))} rounds")
