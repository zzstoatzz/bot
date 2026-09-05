"""Dated run/request receipts; confirmed actions remain in the execution trace."""

import asyncio
import hashlib
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from opentelemetry import trace
from turbopuffer import Turbopuffer

from bot.memory.encounters import ENCOUNTER_NAMESPACE

logger = logging.getLogger(__name__)


@dataclass
class RunEvidence:
    storage: Turbopuffer
    label: str
    event_ids: set[str] = field(default_factory=set)
    id: str = field(default_factory=lambda: f"run-{uuid4()}")
    request_count: int = 0


current_run: ContextVar[RunEvidence | None] = ContextVar[RunEvidence | None](
    "encounter_run", default=None
)


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


async def save_receipt(run: RunEvidence, row: dict) -> None:
    """A telemetry failure is visible in logs, never a fictional receipt."""
    span = trace.get_current_span().get_span_context()
    row = {
        **row,
        "recorded_at": row.get("recorded_at") or timestamp(),
        "run_id": run.id,
        "label": run.label,
        "trace_id": format(span.trace_id, "032x") if span.is_valid else "",
        "event_ids": sorted(run.event_ids),
    }
    try:
        await asyncio.to_thread(
            run.storage.namespace(ENCOUNTER_NAMESPACE).write,
            upsert_rows=[row],
            schema={"event_ids": {"type": "[]string"}},
        )
    except Exception:
        logger.exception("run evidence write failed: %s", row["id"])


async def request_prepared(model: str, instructions: str | None) -> dict | None:
    run = current_run.get()
    if run is None:
        return None
    run.request_count += 1
    text = instructions or ""
    row = {
        "id": f"{run.id}-request-{run.request_count}",
        "kind": "model_request",
        "status": "prepared",
        "model": model,
        "prepared_at": timestamp(),
        "finished_at": "",
        "instruction_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "instruction_chars": len(text),
    }
    await save_receipt(run, row)
    return row


async def request_finished(row: dict | None, status: str) -> None:
    run = current_run.get()
    if run is not None and row is not None:
        await save_receipt(run, {**row, "status": status, "finished_at": timestamp()})


async def run_status(run: RunEvidence, status: str) -> None:
    await save_receipt(
        run,
        {
            "id": f"{run.id}-{status}",
            "kind": "run_status",
            "status": status,
            "recorded_at": timestamp(),
        },
    )
