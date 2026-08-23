"""Process watchdog — exit when the poll loop has stopped doing work.

A failing fly http check only takes the machine out of routing; fly
restarts a machine when its process exits (the ``[[restart]]`` policy in
fly.toml). So ``/health`` reporting 503 is the observability surface and
this is the recovery: the same staleness decision, checked on a timer,
ends the process non-zero.

Every ``/data`` file is written synchronously on the event-loop thread,
so an exit called from this task can never interrupt a write.
"""

import asyncio
import logging
import os
from collections.abc import Callable

from bot.config import settings
from bot.status import BotStatus, bot_status

logger = logging.getLogger("bot.watchdog")

CHECK_INTERVAL = 15.0


def stale_reason(status: BotStatus, stale_after: float) -> str | None:
    """Why the process should be considered wedged, or None if it is fine.

    Paused is deliberate, not a fault: a paused poller that is not running
    is fine, and a paused poller that is running keeps ticking (it still
    fetches notifications, it just does not act on them).
    """
    if not status.polling_active and not status.paused:
        return "poller is not running"
    age = status.last_tick_age_s
    if age is not None and age > stale_after:
        return f"last completed poll was {age:.0f}s ago (limit {stale_after:.0f}s)"
    return None


def exit_process(code: int) -> None:
    logging.shutdown()
    os._exit(code)


async def run(
    exit: Callable[[int], None] = exit_process,
    interval: float = CHECK_INTERVAL,
) -> None:
    while True:
        await asyncio.sleep(interval)
        reason = stale_reason(bot_status, settings.health_stale_after)
        if reason is None:
            continue
        logger.critical(f"watchdog: {reason}; exiting so fly restarts the machine")
        bot_status._save()
        exit(1)
        return
