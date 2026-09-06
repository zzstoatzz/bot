"""Phi-authored private revision notes after classifier rejection."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from bot.core.etiquette import document
from bot.tools._helpers import PhiDeps


def register(agent):
    @agent.tool
    async def document_public_revision(
        ctx: RunContext[PhiDeps],
        attempt_id: Annotated[
            str,
            Field(description="Attempt ID returned by a public classifier rejection"),
        ],
        note: Annotated[
            str,
            Field(
                min_length=1,
                max_length=2000,
                description="Your private account of the rejection and what you will change; stored verbatim, no comic form required",
            ),
        ],
    ) -> str:
        """Document a rejected public attempt before proposing another draft.

        This writes a private journal entry, not a post or a personality revision.
        It does not approve the next draft. Earlier notes cannot be overwritten.
        """
        return document(attempt_id, note)
