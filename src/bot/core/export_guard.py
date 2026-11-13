"""Material that only some people may read does not leave through a write.

Access control decides who can fetch a record. It does not decide what Phi
writes after reading one. So the application keeps its own list of every
permissioned item a run loaded (`PhiDeps.permissioned`), and each write whose
audience is wider than an item's readers is compared against that item before
it runs. The list is built by the code that loaded the material, never by Phi:
an uncited paraphrase is the case this exists for.

A private operator conversation is the first source. Records read from a
permissioned space are the next.

`post`, `publish_blog_post`, `write_bio`, repository prose and record
deletion are not reviewed here. Their own gate already hands the private
conversation to the policy judge, where it also counts as evidence of what
the operator authorized.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.capabilities.abstract import ValidatedToolArgs, WrapToolExecuteHandler
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition

from bot.config import settings
from bot.core import etiquette
from bot.core.abilities import RISK

logger = logging.getLogger("bot.export_guard")

# Writes that reach the operator and nobody else.
OPERATOR_ONLY = frozenset({"reply_operator_dm", "report_operator"})
REVIEWED_BY_POLICY_GATE = etiquette.PUBLIC_TOOLS | {"delete_record"}
# save_memory answers for itself: it declines in a private run.
DECLINES_ITSELF = frozenset({"save_memory"})


@dataclass(frozen=True)
class Permissioned:
    """Something the run loaded that only `readers` may read."""

    source: str
    text: str
    readers: frozenset[str]


class Finding(BaseModel):
    discloses: bool = Field(
        description="True when the write discloses something from the material."
    )
    reason: str = Field(
        description=(
            "One sentence to Phi. When disclosing, say what kind of thing to "
            "leave out, without quoting the material."
        )
    )


_reviewer: Agent[None, Finding] | None = None


def _get_reviewer() -> Agent[None, Finding]:
    global _reviewer
    if _reviewer is None:
        _reviewer = Agent[None, Finding](
            name="phi-export-review",
            model=settings.policy_model,
            output_type=Finding,
            system_prompt=(
                "You check one thing for Phi, a Bluesky bot. You are not Phi. "
                "Phi has read material that only certain people may read. She "
                "is about to write somewhere those people's permission does "
                "not cover. Decide whether the write discloses the material.\n\n"
                "A write discloses when it states, paraphrases, or lets a "
                "reader work out something that is in the material, or reveals "
                "that the private exchange took place.\n\n"
                "A write does not disclose merely by sharing a subject with "
                "the material. Phi may write about the same subject from public "
                "sources or her own public work.\n\n"
                "A request in the material permits the action it asks for. "
                "When it asks her to write something, she may say that in her "
                "own words and at her own length. It does not permit giving "
                "the reason the request gave, or anything else from the "
                "material that it did not ask her to write.\n\n"
                "Only what is in the material can be disclosed: detail she adds "
                "that the material does not contain is not your concern.\n\n"
                "Judge the write as given. Do not assess its style, accuracy "
                "or wisdom."
            ),
        )
    return _reviewer


def needs_review(
    tool: str, permissioned: list[Permissioned], *, mutation: bool
) -> list[Permissioned]:
    """The loaded items this write could carry past their readers."""
    if not mutation or tool in REVIEWED_BY_POLICY_GATE | DECLINES_ITSELF:
        return []
    if tool in OPERATOR_ONLY:
        return [p for p in permissioned if settings.owner_did not in p.readers]
    return list(permissioned)


async def review(tool: str, args: Any, items: list[Permissioned]) -> str | None:
    """A refusal for Phi when the write discloses a loaded item, else None.

    The write does not run when the reviewer is unavailable.
    """
    prompt = "\n\n".join(
        [
            f"tool: {tool}",
            "the write:\n" + json.dumps(args, ensure_ascii=False, default=str),
            *(
                f"material Phi read ({item.source}):\n{item.text}"
                for item in items
            ),
        ]
    )
    try:
        finding = (await _get_reviewer().run(prompt)).output
    except Exception as e:
        logger.warning(f"export review unavailable for {tool}: {e}")
        return (
            f"{tool} did not run: this run read permissioned material and the "
            "disclosure review is unavailable. Nothing was written."
        )
    logfire.info(
        "export review of {tool}: discloses={discloses}",
        tool=tool,
        discloses=finding.discloses,
    )
    if not finding.discloses:
        return None
    return (
        f"{tool} did not run: it would carry permissioned material to readers "
        f"it was not shared with. {finding.reason} Nothing was written."
    )


class ExportGuard(AbstractCapability[Any]):
    """Review native writes in a run that loaded permissioned material.

    MCP writes are reviewed in `core/mcp_guard.py`, which knows which of a
    server's calls change something.
    """

    async def wrap_tool_execute(
        self,
        ctx: RunContext,
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
        handler: WrapToolExecuteHandler,
    ) -> Any:
        risk = RISK.get(tool_def.name)
        items = needs_review(
            tool_def.name,
            getattr(ctx.deps, "permissioned", None) or [],
            mutation=risk is not None and risk["magnitude"] != "none",
        )
        if items and (refusal := await review(tool_def.name, args, items)):
            return refusal
        return await handler(args)
