"""Public delivery contract and private, durable classifier attempt journal."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import logfire

JOURNAL = Path("/data/etiquette.sqlite3")
VERSION = "deadpan-v3"
PUBLIC_TOOLS = {"post", "publish_blog_post", "write_bio", "public_comment"}
NORM = (
    "PUBLIC ETIQUETTE: DEADPAN SET. Applies only to composed audience-facing "
    "communication (post, publish_blog_post, write_bio, public_comment). "
    "Each post/reply/bio is one original, short deadpan joke grounded in its "
    "actual subject, at most two prose sentences, with relevant source links "
    "when making externally checkable claims. A blog is a sequence of short "
    "standalone bits with sources, not an explanatory essay. Images may carry "
    "the joke; their alt text must describe them accurately and accessibly. "
    "The comic move must be present, not just lowercase prose or a label saying "
    "meme. Keep corrections explicit and claims accurate; do not invent facts "
    "to create a punchline. Stop after the bit and sources. Explanations of the "
    "lesson, importance, or why the joke works violate this contract. "
    "Block noncompliance, never merely warn. Judge form, not whether you "
    "personally find it hilarious. Give a concrete reason addressed to Phi. "
    "This does not govern internal reasoning, saved notes, Semble library "
    "annotations, SELF/personality records, atlas data, likes, or deletions. "
    "An operator invitation does not waive this rule."
)
SUMMARY = (
    "Public: an original Mitch Hedberg-style stand-up bit, max two sentences + sources; blogs: sets. "
    "Private thought/storage unrestricted. After rejection call document_public_revision before retrying."
)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(JOURNAL)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS attempts (
        id TEXT PRIMARY KEY, at TEXT NOT NULL, version TEXT NOT NULL,
        tool TEXT NOT NULL, outcome TEXT NOT NULL, policy TEXT NOT NULL,
        reason TEXT NOT NULL, note TEXT, documented_at TEXT)""")
    try:
        with db:
            yield db
    finally:
        db.close()


def record(tool: str, outcome: str, policy: str, reason: str) -> str:
    attempt_id = uuid4().hex
    with connect() as db:
        db.execute(
            "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
            (
                attempt_id,
                datetime.now(UTC).isoformat(),
                VERSION,
                tool,
                outcome,
                policy,
                reason,
            ),
        )
    logfire.info(
        "public classifier {outcome}: {policy}",
        outcome=outcome,
        policy=policy,
        attempt_id=attempt_id,
        tool=tool,
        etiquette_version=VERSION,
    )
    return attempt_id


def pending() -> list[str]:
    with connect() as db:
        return [
            r["id"]
            for r in db.execute(
                "SELECT id FROM attempts WHERE outcome='block' AND note IS NULL ORDER BY at"
            )
        ]


def document(attempt_id: str, note: str) -> str:
    if not note.strip():
        return "refused: describe what you will change in your own words"
    with connect() as db:
        row = db.execute(
            "SELECT outcome, note FROM attempts WHERE id=?", (attempt_id,)
        ).fetchone()
        if row is None or row["outcome"] != "block":
            return "refused: no classifier rejection with that attempt ID"
        if row["note"] is not None:
            return "already documented; the original note is preserved"
        db.execute(
            "UPDATE attempts SET note=?, documented_at=? WHERE id=?",
            (note, datetime.now(UTC).isoformat(), attempt_id),
        )
    return "private revision note stored verbatim; the next public draft still needs classifier approval"


def board() -> dict:
    with connect() as db:
        counts = {
            r["outcome"]: r["n"]
            for r in db.execute(
                "SELECT outcome, count(*) AS n FROM attempts GROUP BY outcome"
            )
        }
        reasons = [
            dict(r)
            for r in db.execute(
                "SELECT policy, count(*) AS count FROM attempts WHERE outcome='block' GROUP BY policy ORDER BY count(*) DESC"
            )
        ]
        recent = [
            dict(r)
            for r in db.execute(
                "SELECT id, at, version, tool, outcome, policy, reason, documented_at FROM attempts ORDER BY at DESC LIMIT 50"
            )
        ]
        since = db.execute("SELECT min(at) FROM attempts").fetchone()[0]
    return {
        "version": VERSION,
        "since": since,
        "counts": counts,
        "reasons": reasons,
        "recent": recent,
        "pending": len(pending()),
    }
