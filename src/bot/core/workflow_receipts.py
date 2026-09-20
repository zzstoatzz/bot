"""Private workflow receipts share the operator journal, not public state."""

import hashlib
import json
from datetime import UTC, datetime

from bot.core.operator_reports import connect


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS workflow_requests (
        request_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
        workflow TEXT NOT NULL, repo TEXT NOT NULL, requested REAL NOT NULL,
        source_message TEXT NOT NULL, state TEXT NOT NULL,
        flow_run_id TEXT, run_name TEXT)""")


def reserve(payload: dict, source_message: str) -> dict:
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    with connect() as db:
        _table(db)
        db.execute(
            "INSERT OR IGNORE INTO workflow_requests VALUES (?,?,?,?,?,?,?,NULL,NULL)",
            (
                payload["request_key"],
                fingerprint,
                payload["workflow"],
                payload["repo"],
                datetime.now(UTC).timestamp(),
                source_message,
                "unconfirmed",
            ),
        )
        row = db.execute(
            "SELECT * FROM workflow_requests WHERE request_key=?",
            (payload["request_key"],),
        ).fetchone()
        if row["fingerprint"] != fingerprint:
            raise ValueError("Request key already identifies different work")
        return dict(row)


def confirm(key: str, run_id: str, name: str) -> None:
    with connect() as db:
        _table(db)
        db.execute(
            "UPDATE workflow_requests SET state='queued',flow_run_id=?,run_name=? "
            "WHERE request_key=?",
            (run_id, name, key),
        )


def recent(key: str = "") -> list[dict]:
    with connect() as db:
        _table(db)
        if key:
            rows = db.execute(
                "SELECT * FROM workflow_requests WHERE request_key=?", (key,)
            )
        else:
            rows = db.execute(
                "SELECT * FROM workflow_requests ORDER BY requested DESC LIMIT 10"
            )
        return [{k: row[k] for k in row.keys() if k != "fingerprint"} for row in rows]
