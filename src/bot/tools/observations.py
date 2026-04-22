"""Active-observation tools — record + drop.

Active observations are phi's small attention pool, surfaced in the prompt
next to GOALS. Phi adds via observe; removes via drop_observation. Aging
is automatic when the cap is exceeded.
"""

from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from bot.core import observations
from bot.core.atproto_client import bot_client
from bot.tools._helpers import PhiDeps


def register(agent):
    @agent.tool
    async def observe(
        ctx: RunContext[PhiDeps],
        content: Annotated[
            str,
            Field(
                description=(
                    "What you noticed, in your own voice. Stays factual — "
                    "the change observed, not theories about cause."
                )
            ),
        ],
        reasoning: Annotated[
            str,
            Field(
                description=(
                    "Optional: why this is worth keeping in active attention "
                    "— what might compose with it, what it shifts, why it "
                    "caught your eye. Empty is fine."
                )
            ),
        ] = "",
    ) -> str:
        """Record an active observation in your attention pool.

        Use when you've noticed something worth holding but not yet acting on
        — a relay transition, a thread direction, a person showing up
        repeatedly, a pattern across posts. The observation stays visible to
        you in the [ACTIVE OBSERVATIONS] block of every subsequent run, so
        you can naturally weave it into a later musing or reply.

        The pool is bounded (5 active). Older observations age out into a
        searchable archive — they're not lost, just no longer in your
        working set.
        """
        try:
            uri = await observations.record_observation(
                bot_client, ctx.deps.memory, content, reasoning
            )
            return f"observed: {uri}"
        except Exception as e:
            return f"failed to record observation: {e}"

    @agent.tool
    async def drop_observation(
        ctx: RunContext[PhiDeps],
        rkey: Annotated[
            str,
            Field(
                description=(
                    "The rkey of the active observation to drop. Get rkeys "
                    "from the [ACTIVE OBSERVATIONS] block in your prompt."
                )
            ),
        ],
        reason: Annotated[
            str,
            Field(
                description=(
                    "Why you're dropping it — posted about it / no longer "
                    "relevant / decided not to surface / etc. Goes into the "
                    "archive for later introspection."
                )
            ),
        ],
    ) -> str:
        """Explicitly remove an observation from your active pool.

        Use when you've acted on an observation (posted about it, brought it
        into a reply) or decided it's not worth carrying. The observation is
        archived with your reason — searchable later, not deleted.
        """
        try:
            ok = await observations.drop_observation(
                bot_client, ctx.deps.memory, rkey, reason
            )
            if not ok:
                return f"no active observation with rkey {rkey}"
            return f"dropped {rkey} ({reason})"
        except Exception as e:
            return f"failed to drop observation: {e}"
