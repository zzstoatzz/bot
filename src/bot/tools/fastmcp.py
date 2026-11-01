"""Read the operator's fastmcp triage state on demand."""

import logging
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from bot.core.fastmcp_triage import fetch_triage, format_triage
from bot.tools._helpers import PhiDeps

logger = logging.getLogger("bot.tools.fastmcp")


def register(agent):
    @agent.tool
    async def inspect_fastmcp_triage(
        ctx: RunContext[PhiDeps],
        weeks: Annotated[
            int,
            Field(description="How many weeks of history to show (1-52).", ge=1, le=52),
        ] = 12,
        stuck_limit: Annotated[
            int,
            Field(description="How many stuck PRs to list, oldest first (1-50).", ge=1, le=50),
        ] = 15,
    ) -> str:
        """Read PrefectHQ/fastmcp's triage state from the operator's warehouse.

        The operator maintains fastmcp. Shows open issues and PRs by age,
        weekly intake against merges and closures, how contributor PRs fare
        by the week they were opened (split by whether the triage reviewer
        looked at them), and the contributor PRs waiting longest on a
        maintainer. Synced hourly from GitHub; public data.
        """
        try:
            return format_triage(await fetch_triage(weeks, stuck_limit))
        except Exception as e:
            logger.warning(f"fastmcp triage fetch failed: {type(e).__name__}: {e}")
            return f"fastmcp triage unavailable: {type(e).__name__}: {e}"
