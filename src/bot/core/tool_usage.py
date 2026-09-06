"""Durable tool exposure and invocation metadata; never arguments or results."""

import asyncio
import logging
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from opentelemetry import trace
from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.capabilities.abstract import ValidatedToolArgs, WrapToolExecuteHandler
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import ToolDefinition

from bot.config import settings
from bot.core.abilities import RISK

JOURNAL = Path("/data/tool_usage.sqlite3")
logger = logging.getLogger(__name__)


@contextmanager
def connect():
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(JOURNAL, timeout=10)
    try:
        with db:
            db.row_factory = sqlite3.Row
            db.execute(
                "CREATE TABLE IF NOT EXISTS offers (run TEXT, step INTEGER, tool TEXT, at TEXT, trace TEXT, PRIMARY KEY(run,step,tool))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS calls (run TEXT, call TEXT, tool TEXT, at TEXT, trace TEXT, outcome TEXT, PRIMARY KEY(run,call))"
            )
            yield db
    finally:
        db.close()


def record_offers(run: str, step: int, names: list[str], trace_id: str):
    now = datetime.now(UTC)
    with connect() as db:
        db.executemany(
            "INSERT OR IGNORE INTO offers VALUES (?,?,?,?,?)",
            [(run, step, n, now.isoformat(), trace_id) for n in names],
        )
        cutoff = (now - timedelta(days=30)).isoformat()
        db.execute("DELETE FROM offers WHERE at < ?", (cutoff,))
        db.execute("DELETE FROM calls WHERE at < ?", (cutoff,))


def record_call(run: str, call: str, name: str, trace_id: str, outcome: str):
    with connect() as db:
        db.execute(
            "INSERT INTO calls VALUES (?,?,?,?,?,?) ON CONFLICT(run,call) DO UPDATE SET outcome=excluded.outcome",
            (run, call, name, datetime.now(UTC).isoformat(), trace_id, outcome),
        )


def board():
    cutoff = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    with connect() as db:
        offers = {
            r["tool"]: dict(r)
            for r in db.execute(
                "SELECT tool, count(*) requests, count(DISTINCT run) runs, max(at) last_offered FROM offers WHERE at >= ? GROUP BY tool",
                (cutoff,),
            )
        }
        calls = {
            r["tool"]: dict(r)
            for r in db.execute(
                "SELECT tool, count(*) calls, sum(outcome='returned') returned, sum(outcome='raised') raised, sum(outcome='started') unfinished, max(at) last_called FROM calls WHERE at >= ? GROUP BY tool",
                (cutoff,),
            )
        }
        recent = [
            dict(r)
            for r in db.execute(
                "SELECT tool, at, trace, outcome FROM calls WHERE at >= ? ORDER BY at DESC LIMIT 40",
                (cutoff,),
            )
        ]
        since = db.execute(
            "SELECT min(at) FROM offers WHERE at >= ?", (cutoff,)
        ).fetchone()[0]
    tools = []
    for name in sorted(set(RISK) | set(offers) | set(calls)):
        offered, called = offers.get(name, {}), calls.get(name, {})
        tools.append(
            {
                "name": name,
                "native": name in RISK,
                "requests": offered.get("requests", 0),
                "runs": offered.get("runs", 0),
                "calls": called.get("calls", 0),
                "returned": called.get("returned", 0),
                "raised": called.get("raised", 0),
                "unfinished": called.get("unfinished", 0),
                "last_offered": offered.get("last_offered"),
                "last_called": called.get("last_called"),
            }
        )
    for row in recent:
        row["trace_url"] = (
            f"{settings.logfire.ui_url}/?q=trace_id%3D%27{row['trace']}%27"
            if row["trace"] and settings.logfire.ui_url
            else None
        )
    return {"since": since, "window_days": 30, "tools": tools, "recent": recent}


async def observe(fn, *args):
    try:
        await asyncio.to_thread(fn, *args)
    except Exception:
        logger.exception("Tool usage observation failed; agent behavior unchanged")


def trace_id():
    span = trace.get_current_span().get_span_context()
    return format(span.trace_id, "032x") if span.is_valid else ""


class ToolUsage(AbstractCapability):
    async def before_model_request(
        self, ctx: RunContext, request_context: ModelRequestContext
    ) -> ModelRequestContext:
        if ctx.run_id:
            await observe(
                record_offers,
                ctx.run_id,
                ctx.run_step,
                [
                    t.name
                    for t in request_context.model_request_parameters.function_tools
                ],
                trace_id(),
            )
        return request_context

    async def wrap_tool_execute(
        self,
        ctx: RunContext,
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
        handler: WrapToolExecuteHandler,
    ) -> Any:
        run = ctx.run_id or trace_id()
        tid = trace_id()
        await observe(
            record_call, run, call.tool_call_id, tool_def.name, tid, "started"
        )
        try:
            result = await handler(args)
        except BaseException:
            await observe(
                record_call, run, call.tool_call_id, tool_def.name, tid, "raised"
            )
            raise
        await observe(
            record_call, run, call.tool_call_id, tool_def.name, tid, "returned"
        )
        return result
