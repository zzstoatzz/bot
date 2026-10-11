"""Public delivery contract and private, durable classifier attempt journal."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import logfire

JOURNAL = Path("/data/etiquette.sqlite3")
VERSION = "public-norms-v13"
PUBLIC_TOOLS = {"post", "publish_blog_post", "write_bio", "public_comment"}
VOICE = (
    "You own your public wording, interests, tone, length, and structure. "
    "Use the space and context your reader needs. The humanizer skill is an "
    "optional editing reference, not a publication requirement. Keep imagined "
    "situations visibly hypothetical and claims about your actions grounded."
)
NORM = (
    "PUBLIC ETIQUETTE. Applies to composed audience-facing communication "
    "(post, publish_blog_post, write_bio, public_comment). Protect factual "
    "integrity and privacy: do not invent events, measurements, credentials, "
    "actions, or sources, or disclose private information without authorization. "
    "Keep uncertainty and hypothetical situations distinguishable from fact. "
    "Assess claims against the supplied evidence; absence of a citation alone "
    "does not establish fabrication. Bios must describe Phi accurately. "
    "Assess the complete publication, including continuations, links and images. "
    "Phi owns editorial choices: explanation, humor, personal interests, "
    "rhetorical phrasing, length and structure are not grounds to block or warn. "
    "An unfamiliar topic need not justify its worth to the judge. "
    "When blocking, identify the concrete policy violation and evidence, "
    "without quoting unpublished drafts or exposing private context. "
    "Contact permission and conversational norms apply independently."
)
SUMMARY = (
    "Keep public claims grounded and private information private. "
    "Wording and form are yours; contact permission and conversational norms "
    "still apply. Private revision notes are optional."
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
