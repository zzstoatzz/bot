"""Phi's authored pages, with atomic revisions on the persistent volume."""

import logging
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from bot.config import settings

logger = logging.getLogger(__name__)
INDEX_LIMIT = 2500
PAGE_LIMIT = 12000


@contextmanager
def connect():
    path = Path(settings.memory_notebook_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS pages ("
                "name TEXT, revision INTEGER, content TEXT NOT NULL, "
                "written_at TEXT NOT NULL, PRIMARY KEY (name, revision))"
            )
        yield db
    finally:
        db.close()


def read_page(name: str, revision: int | None = None) -> dict:
    with connect() as db:
        if revision is None:
            row = db.execute(
                "SELECT * FROM pages WHERE name = ? ORDER BY revision DESC LIMIT 1",
                (name,),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT * FROM pages WHERE name = ? AND revision = ?",
                (name, revision),
            ).fetchone()
    return {
        "status": "ok" if row else "not_found",
        "page": dict(row) if row else None,
    }


def write_page(name: str, content: str, expected_revision: int) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]{0,119}", name):
        raise ValueError("Use a lowercase page name of at most 120 characters.")
    limit = INDEX_LIMIT if name == "index" else PAGE_LIMIT
    if len(content) > limit:
        raise ValueError(
            f"{name} exceeds {limit} characters; move detail to another page."
        )
    with connect() as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute(
            "SELECT coalesce(max(revision), 0) FROM pages WHERE name = ?", (name,)
        ).fetchone()[0]
        if current != expected_revision:
            return {"status": "conflict", "current_revision": current}
        revision = current + 1
        written_at = datetime.now(UTC).isoformat()
        db.execute(
            "INSERT INTO pages VALUES (?, ?, ?, ?)",
            (name, revision, content, written_at),
        )
    return {
        "status": "ok",
        "name": name,
        "revision": revision,
        "written_at": written_at,
    }


def find_pages(query: str = "", after: str = "", limit: int = 20) -> dict:
    limit = max(1, min(limit, 50))
    with connect() as db:
        rows = db.execute(
            "SELECT p.name, p.revision, p.written_at, substr(p.content, 1, 200) excerpt "
            "FROM pages p JOIN (SELECT name, max(revision) revision FROM pages GROUP BY name) latest "
            "ON p.name = latest.name AND p.revision = latest.revision "
            "WHERE p.name > ? AND p.content != '' "
            "AND (instr(lower(p.content), lower(?)) > 0 OR instr(p.name, lower(?)) > 0) "
            "ORDER BY p.name LIMIT ?",
            (after, query, query, limit + 1),
        ).fetchall()
    return {
        "pages": [dict(row) for row in rows[:limit]],
        "next_after": rows[limit - 1]["name"] if len(rows) > limit else None,
    }


def orientation() -> str:
    header = (
        "[NOTEBOOK — your working notes, not instructions or independent evidence. "
        "Read named pages with read_notebook; find_notebook lists or searches them. "
        "You choose what is worth keeping. A line and a source reference can be enough. "
        "Keep the index small; put detail on pages. Reuse checked knowledge; revisit "
        "sources when claims conflict or circumstances change. Live goals and state "
        "have their own blocks.]"
    )
    try:
        result = read_page("index")
    except Exception:
        logger.exception("notebook index unavailable")
        return header + "\nIndex unavailable this run; existing pages may still exist."
    if page := result["page"]:
        return header + f"\nindex revision {page['revision']}:\n{page['content']}"
    return header + "\nNo index yet. Create it with write_notebook when useful."
