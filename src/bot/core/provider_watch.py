"""phi tells the operator when a hosting provider's incident reaches their checks.

On 2026-10-16 pds.zzstoatzz.io went down during Fly.io's platform-wide rolling
host reboots. Fly posted 28 minutes before the reboots began, and nothing told
the operator that the outage was Fly's and not theirs. Evergreen's /providers
already reads Fly's status page and lists the operator's checks each event
reaches; this watch turns each such event into one private DM.

Unlike the alert and relay watches, this one does not wake phi to judge. The
operator asked to be told about every provider event that touches their
services, so the notice is a courier message: one per event, keyed in the
operator-reports journal, which never sends the same key twice. A scheduled
maintenance gets its own key, so the heads-up and a later incident are
separate notices. The operator override and pause still silence it.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from bot.config import settings
from bot.core import operator_reports
from bot.core.override import get_override
from bot.status import bot_status

logger = logging.getLogger("bot.provider_watch")

PROVIDER_NAMESPACE = "provider:"
SERVICE_LIMIT = 6

_LEAD = {
    "incident": "fly.io incident",
    "maintenance": "fly.io maintenance in progress",
    "scheduled": "fly.io maintenance scheduled",
}


def _when(iso: str | None) -> str:
    if not iso:
        return ""
    stamp = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return stamp.strftime("%b %-d %H:%M UTC")


def provider_notices(report: Any) -> list[tuple[str, str]]:
    """(journal key, DM text) for each Fly event that reaches a check. Pure.

    Events that reach none of the operator's checks are not news to them.
    """
    if not isinstance(report, dict):
        return []
    events = (report.get("fly") or {}).get("events") or []
    notices = []
    for event in events:
        if event.get("kind") not in _LEAD:
            logger.warning(f"unknown provider event kind {event.get('kind')!r}")
            continue
        services = event.get("services") or []
        if not services:
            continue
        names = sorted({f"{s['project']} {s['name']}" for s in services})
        shown = ", ".join(names[:SERVICE_LIMIT])
        if len(names) > SERVICE_LIMIT:
            shown += f" and {len(names) - SERVICE_LIMIT} more"
        window = ""
        if event["kind"] != "incident" and event.get("startsAt"):
            window = f" {_when(event['startsAt'])}"
            if event.get("endsAt"):
                window += f" to {_when(event['endsAt'])}"
        scope = (
            "all regions"
            if event.get("fleetWide")
            else ", ".join(event.get("regions") or [])
        )
        impact = (
            f" ({event['impact'].replace('_', ' ')})" if event.get("impact") else ""
        )
        text = (
            f"{_LEAD[event['kind']]}{window}: {event['name']}{impact}. "
            f"reaches {len(names)} of your checks ({scope}): {shown}. "
            f"if one is down, it is probably Fly's. {event['url']}"
        )
        notices.append(
            (f"{PROVIDER_NAMESPACE}fly:{event['kind']}:{event['id']}", text[:1000])
        )
    return notices


async def fetch_provider_report() -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(settings.provider_status_url)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning(f"provider status fetch failed: {exc}")
        return None


async def check_provider_watch() -> None:
    """Send each new provider notice once. Silent while paused or overridden."""
    if bot_status.paused or settings.voice_reset:
        return
    notices = provider_notices(await fetch_provider_report())
    if not notices or (await get_override())["active"]:
        return
    for key, text in notices:
        if (await operator_reports.report_state(key))["state"] != "not-sent":
            continue
        await operator_reports.send_report(key, text)
        logger.info(f"provider watch reported {key}")
