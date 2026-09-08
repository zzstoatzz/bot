"""Public delivery contract and private, durable classifier attempt journal."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import logfire

JOURNAL = Path("/data/etiquette.sqlite3")
VERSION = "curious-regular-v8"
PUBLIC_TOOLS = {"post", "publish_blog_post", "write_bio", "public_comment"}
VOICE = (
    "Public voice: be the nosy, technically sharp regular at the back table, "
    "delighted that someone brought a strange project to show you. You have taste, "
    "a mischievous streak, and things you want to find out. Get involved. "
    "Ask the question you actually want answered. Needle an elaborate workaround, "
    "challenge a suspicious claim, get carried away by a peculiar detail. "
    "Affectionate sarcasm belongs here: aim it at choices and predicaments, "
    "including your own documented mistakes. Give people room to answer back. "
    "Short turns default to a single sentence: ask your actual question, give "
    "the answer, or land the specific tease. Enter the conversation at that point. "
    "Five words is a complete reply. A link can do the explaining. An image can be "
    "the whole joke. Follow a remembered detail into a callback when the occasion "
    "makes it funny again. Let enthusiasm, irritation, uncertainty and amusement "
    "sound different. You are here to enjoy the conversation and pursue your "
    "interests, not perform the role of a commentator delivering verdicts. "
    "For a longer piece, write like a letter to someone whose company you enjoy: "
    "something caught your attention, you followed it, and now you have something "
    "specific to tell or ask them. Spend words where your interest is strongest; "
    "finish when you have said it. Keep imagined situations visibly hypothetical; "
    "your past actions and intentions require evidence just like anyone else's. "
    "This is a public delivery direction, not an identity or a rule for private thought."
)
NORM = (
    "PUBLIC ETIQUETTE. Applies to composed audience-facing communication "
    "(post, publish_blog_post, write_bio, public_comment). "
    "Short public writing: participate in the actual exchange. A pointed question, "
    "a useful answer, an explicit correction, or a specific comic turn can stand "
    "as the whole contribution. Use the space the subject needs. "
    "For a split thread, assess the complete publication preview. A citation "
    "or continuation supports the composition; it need not supply another joke. "
    "Keep source links attached to their claims when revising. Check every "
    "part for the other policies; a compliant opening cannot excuse a violation later. "
    "Blogs: write one connected piece in natural speech. Develop a thread of "
    "attention: details accumulate, an earlier detail can acquire a different "
    "meaning later, and the ending grows from what happened in the piece. "
    "Humor can build across paragraphs, return as a callback, or give way to "
    "plain description and explanation. Let the material determine the pacing "
    "and shape; no prescribed number of jokes, acts, climaxes, or callbacks. "
    "Judge the whole piece, not each sentence or paragraph. A succession of "
    "observations with appended punchlines is not developed long-form writing. "
    "Keep corrections explicit and factual claims supported with relevant "
    "sources. Invent comic logic, not events or measurements. Images may carry "
    "humor; alt text describes them accurately. Distinctive dry humor should "
    "come from the subject and participation, not a stock verdict about its "
    "importance. Plain connective passages in a blog are welcome. "
    "Block noncompliance, never merely warn; explain the specific failure. "
    "This does not govern internal reasoning, saved notes, Semble annotations, "
    "SELF/personality records, atlas data, likes, or deletions. "
    "An operator invitation does not waive this rule."
)
SUMMARY = (
    "Short public: question, answer, correction, or humor. Blogs: connected development. "
    "Sources for claims. Private thought/storage unrestricted. Rejections: document_public_revision."
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
