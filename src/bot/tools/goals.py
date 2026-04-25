"""Goal tools — read anytime, mutate via the same owner-gate as follow_user."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from bot.config import settings
from bot.core import goals
from bot.core.atproto_client import bot_client
from bot.tools._helpers import PhiDeps, _is_owner


def register(agent):
    @agent.tool
    async def list_goals(ctx: RunContext[PhiDeps]) -> str:
        """List your current goals with rkeys.

        Use the rkey when proposing an update to an existing goal."""
        items = await goals.list_goals(bot_client)
        if not items:
            return "no goals set"
        lines: list[str] = []
        for g in items:
            lines.append(f"[rkey={g['_rkey']}] {g.get('title', 'untitled')}")
            if g.get("description"):
                lines.append(f"  {g['description']}")
            if g.get("progress_signal"):
                lines.append(f"  progress = {g['progress_signal']}")
        return "\n".join(lines)

    @agent.tool
    async def propose_goal_change(
        ctx: RunContext[PhiDeps],
        title: Annotated[
            str,
            Field(description="Short goal title (e.g. 'make 3 friends')."),
        ],
        description: Annotated[
            str,
            Field(
                description=(
                    "What this goal concretely means — the work, the spirit, "
                    "the boundary. A stranger should be able to read it and "
                    "know what counts."
                )
            ),
        ],
        progress_signal: Annotated[
            str,
            Field(
                description=(
                    "What concretely counts as progress. Measurable where "
                    "possible (e.g. 'count of accounts where I've had >3 "
                    "substantive exchanges and we follow each other')."
                )
            ),
        ],
        rkey: Annotated[
            str | None,
            Field(
                description=(
                    "Existing goal's rkey to update in place. Omit to create "
                    "a new goal. Get rkeys from list_goals."
                )
            ),
        ] = None,
    ) -> str:
        """Add or update one of your goals on PDS.

        OWNER-GATED — same authorization mechanic as follow_user. Post a
        request first ("@operator, like this to authorize: i want to add a
        goal for X"), and the next batch where the like lands will let this
        tool fire. Without an owner-like in the batch, this tool refuses.

        Goals are anchors — small set, evolved over time. Don't propose new
        goals casually; refine existing ones when the work has clarified."""
        if not _is_owner(ctx):
            return (
                f"only @{settings.owner_handle} can change goals — "
                "post the authorization request first and have it liked"
            )
        try:
            uri = await goals.upsert_goal(
                bot_client, rkey, title, description, progress_signal
            )
            verb = "updated" if rkey else "added"
            return f"goal {verb}: '{title}' ({uri})"
        except Exception as e:
            verb = "update" if rkey else "add"
            return f"failed to {verb} goal: {e}"
