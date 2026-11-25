"""Receive private MCP recovery evidence and report persistent outages."""

import asyncio
import ipaddress
import logging
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import logfire
from fastmcp import Client
from fastmcp_events import EventsClientExtension, poll_events_mcp
from pydantic import AwareDatetime, BaseModel, Field

from bot.config import settings
from bot.core import operator_reports
from bot.core.override import get_override
from bot.core.policy import check_action
from bot.status import bot_status

EVENT_NAME = "incident.recovery_failed"
POLLZ_HEALTH = "https://api.pollz.waow.tech/health"
TAILNET = ipaddress.ip_network("100.64.0.0/10")
PREFECT_RUN_PREFIX = "https://prefect-server.waow.tech/runs/flow-run/"
logger = logging.getLogger("bot.recovery-events")


class RecoveryFailed(BaseModel):
    machine: str = Field(pattern=r"^[a-z0-9]+$", max_length=40)
    release: str | None = Field(default=None, max_length=128)
    attempts: int = Field(gt=0)
    exit_code: int | None = None
    oom_killed: bool
    failed_at: AwareDatetime
    sweep_url: str | None = Field(default=None, max_length=256)


def allowed_endpoint(url: str) -> bool:
    parts = urlsplit(url)
    if (
        parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path != "/phi/mcp"
        or not parts.hostname
    ):
        return False
    if parts.scheme == "https":
        return True
    try:
        return (
            parts.scheme == "http" and ipaddress.ip_address(parts.hostname) in TAILNET
        )
    except ValueError:
        return False


def checkpoint(endpoint: str, update: str | None = None) -> str | None:
    with operator_reports.connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS recovery_watch (endpoint TEXT PRIMARY KEY, cursor TEXT NOT NULL)"
        )
        if update is not None:
            db.execute(
                "INSERT INTO recovery_watch VALUES (?, ?) "
                "ON CONFLICT(endpoint) DO UPDATE SET cursor=excluded.cursor",
                (endpoint, update),
            )
            return update
        row = db.execute(
            "SELECT cursor FROM recovery_watch WHERE endpoint=?", (endpoint,)
        ).fetchone()
        return row["cursor"] if row else None


async def available() -> bool:
    return not (
        bot_status.paused or settings.voice_reset or (await get_override())["active"]
    )


def report_text(data: RecoveryFailed, status: int, checked_at: datetime) -> str:
    reason = "an OOM kill" if data.oom_killed else f"process exit {data.exit_code}"
    step = (
        "Check Cellar's memory use and limit before bringing it back up."
        if data.oom_killed
        else "Inspect Cellar's last crash log before bringing it back up."
    )
    reason += f" on machine {data.machine}"
    text = (
        f"Pollz still returned HTTP {status} at {checked_at:%H:%M UTC}. "
        f"Fly exhausted {data.attempts} Cellar restart retries after {reason} "
        f"at {data.failed_at.astimezone(UTC):%H:%M UTC}. {step}"
    )
    if data.release and all(
        ch.isascii() and (ch.isalnum() or ch in "-._:") for ch in data.release
    ):
        text += f" Machine version: {data.release}."
    if data.sweep_url and data.sweep_url.startswith(PREFECT_RUN_PREFIX):
        suffix = data.sweep_url.removeprefix(PREFECT_RUN_PREFIX)
        try:
            validated = UUID(suffix)
        except ValueError:
            pass
        else:
            text += f" Fleet check: {PREFECT_RUN_PREFIX}{validated}"
    return text


async def current_health() -> int:
    async with (
        httpx.AsyncClient(timeout=10, follow_redirects=False) as http,
        http.stream("GET", POLLZ_HEALTH) as response,
    ):
        return response.status_code


async def handle_recovery(event_id: UUID, data: RecoveryFailed) -> bool:
    """Return whether it is safe to acknowledge this event."""
    key = f"note:recovery-{event_id}"
    with logfire.span("recovery failed", event_id=str(event_id)):
        previous = operator_reports.delivery_record(key)
        if previous["state"] != "not-sent":
            logger.info(
                "Recovery event has an existing private receipt (%s)", previous["state"]
            )
            return True
        if not await available():
            return False
        status = await current_health()
        if 200 <= status < 300:
            logger.info("Pollz recovered before Phi handled the event")
            return True
        if status < 500:
            raise RuntimeError("Pollz health returned an inconclusive status")
        checked_at = datetime.now(UTC)
        text = report_text(data, status, checked_at)
        verdict = await check_action(
            action=f"Private Bluesky DM to operator: {text}",
            provenance=(
                "The operator requested one private recovery report only after "
                "Fly exhausted automatic restart and a new health probe still failed. "
                "Fly lifecycle fields and a fresh Pollz HTTP probe corroborate this."
            ),
            tool="report_operator",
        )
        if verdict["verdict"] == "block":
            logger.warning("Recovery report blocked by the private delivery judge")
            return True
        if verdict["verdict"] != "allow" or not await available():
            return False
        receipt = await operator_reports.send_report(key, text)
        logger.info("Recovery report receipt: %s", receipt["state"])
        return receipt["state"] != "not-sent"


async def poll_once(endpoint: str, client: Client) -> float:
    cursor = checkpoint(endpoint)
    async with client:
        batch = await poll_events_mcp(client, EVENT_NAME, cursor=cursor, max_events=1)
    if batch.cursor is None:
        raise RuntimeError("Recovery feed did not supply a replay cursor")
    if batch.truncated:
        logger.warning("Recovery feed resumed past its retained history")
    if len(batch.events) > 1:
        raise RuntimeError("Recovery feed exceeded the requested batch size")
    for event in batch.events:
        if event.name != EVENT_NAME:
            raise RuntimeError("Unexpected event in the private recovery feed")
        if not await handle_recovery(
            UUID(event.event_id), RecoveryFailed.model_validate(event.data)
        ):
            return 30
    checkpoint(endpoint, batch.cursor)
    return 1 if batch.has_more else max(15, min(120, batch.next_poll_ms / 1000))


async def watch(endpoint: str, token: str) -> None:
    client = Client(
        endpoint,
        auth=token,
        extensions=[EventsClientExtension()],
        mode="auto",
        timeout=25,
    )
    delay = 15.0
    while True:
        try:
            delay = await poll_once(endpoint, client) if await available() else 30
        except Exception as exc:
            logger.warning(
                "Private recovery event poll failed (%s); keeping cursor",
                type(exc).__name__,
            )
            delay = min(120, delay * 2)
        await asyncio.sleep(delay)


def start_recovery_watch() -> asyncio.Task | None:
    endpoint = settings.recovery_mcp_url
    token = settings.recovery_mcp_token
    if not endpoint and not token:
        return None
    if (
        not endpoint
        or not token
        or not allowed_endpoint(endpoint)
        or len(token.get_secret_value()) < 32
    ):
        logger.error(
            "Private recovery event watch has an invalid URL or missing bearer"
        )
        return None
    return asyncio.create_task(
        watch(endpoint, token.get_secret_value()), name="recovery-events"
    )
