"""Phi authors the personality used by her next run."""

from typing import Annotated

from pydantic import Field

from bot.core.atproto_client import bot_client
from bot.core.override import get_override, refusal_text
from bot.core.personality import MAX_CHARS
from bot.core.personality import write_personality as save_personality


def register(agent):
    @agent.tool
    async def write_personality(
        text: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MAX_CHARS,
                description="Complete replacement personality.",
            ),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=1000,
                description="Why you are making this change.",
            ),
        ],
    ) -> str:
        """Replace your personality directly; no pull request or operator like needed.

        Describe the disposition you want to inhabit. Keep named influences and
        their examples in choose-influences. This changes the next run, not the
        current conversation's instructions. Earlier revisions remain on your
        PDS; restore one by writing its text as a new revision. Operational rules
        and the operator pause remain separate. Read the revise-personality skill
        for the operator's explanation and experiment results.
        """
        override = await get_override()
        if override["active"]:
            return refusal_text(override)
        uri = await save_personality(bot_client, text, reason)
        return f"Personality saved for the next run: {uri}. Earlier revisions retained."
