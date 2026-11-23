"""Episodic reconciliation and schemas for retained memory records."""

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from turbopuffer.types import AttributeSchemaConfigParam, AttributeSchemaDropParam

from bot.config import settings
from bot.core.model_health import checked


class ReconciliationAction(BaseModel):
    """Decision for how a new observation relates to the existing ones."""

    action: str = Field(description="one of: ADD, UPDATE, DELETE, NOOP")
    targets: list[int] = Field(
        default_factory=list,
        description=(
            "numbers of the EXISTING observations the action applies to. empty for ADD."
        ),
    )
    new_content: str | None = Field(
        default=None, description="merged content when action is UPDATE"
    )
    new_tags: list[str] | None = Field(
        default=None, description="merged tags when action is UPDATE"
    )
    reason: str = Field(description="brief explanation of the decision")


class ReconciliationResult(BaseModel):
    """Result of reconciling a new observation against its nearest neighbours."""

    decision: ReconciliationAction


RECONCILIATION_SYSTEM_PROMPT = """\
You reconcile a NEW observation against up to three EXISTING observations from memory, numbered nearest first.

Decide one action, and list in `targets` the numbers of the existing observations it applies to:
- ADD: the new observation contains genuinely different information from every existing one. keep them all. no targets.
- UPDATE: the new observation refines, corrects, or supersedes the targets. return merged content and tags; that one row replaces every target.
- DELETE: the targets are wrong, outdated, or fully redundant given the new one. the new one will be stored separately.
- NOOP: the new observation adds nothing beyond the target. discard it.

Judge each existing observation on its own. One that is merely about the same topic is not a target; only target what the new observation actually restates, refines, or contradicts. If the new observation contradicts or replaces more than one, target all of them.
Two observations about different things of the same kind (two projects, two tools, two places, two events) are both true: that is ADD, even when the wording is close. A target is replaced, so everything in it that is still true must survive in the merged content.
Write merged content the way the observations are written: lowercase, one fact, no longer than it needs to be.
Corrections (e.g., "name is sam, corrected from previous error") always win over the entries they correct — use UPDATE or DELETE.
When in doubt between ADD and NOOP, prefer NOOP. memory should be lean."""


def reconciliation_prompt(
    existing: Sequence[Mapping], content: str, tags: list[str]
) -> str:
    listed = "\n\n".join(
        f"EXISTING {n}: {row['content']}\nEXISTING {n} tags: {row['tags']}"
        for n, row in enumerate(existing, start=1)
    )
    return f"{listed}\n\nNEW observation: {content}\nNEW tags: {tags}"


def reconciliation_targets[T](
    decision: ReconciliationAction, existing: Sequence[T]
) -> list[T]:
    """The existing rows a decision names, nearest first, falling back to the
    nearest when the reconciler names none or only numbers never offered."""
    picked = [
        existing[n - 1]
        for n in sorted(set(decision.targets))
        if 1 <= n <= len(existing)
    ]
    return picked or list(existing[:1])


_reconciliation_agent: Agent[None, ReconciliationResult] | None = None


def get_reconciliation_agent() -> Agent[None, ReconciliationResult]:
    global _reconciliation_agent
    if _reconciliation_agent is None:
        _reconciliation_agent = Agent[None, ReconciliationResult](
            name="observation-reconciler",
            model=checked(settings.extraction_model),
            output_type=ReconciliationResult,
            system_prompt=RECONCILIATION_SYSTEM_PROMPT,
        )
    agent = _reconciliation_agent
    assert agent is not None
    return agent


EPISODIC_SCHEMA: dict[
    str, str | AttributeSchemaConfigParam | AttributeSchemaDropParam
] = {
    "content": {"type": "string", "full_text_search": True},
    "tags": {"type": "[]string", "filterable": True},
    "source": {"type": "string", "filterable": True},  # "tool", "run:<label>", ...
    "source_uris": {"type": "[]string"},  # AT-URIs backing this memory (optional)
    "created_at": {"type": "string"},
    "status": {"type": "string", "filterable": True},  # active, superseded
    "retired_reason": {"type": "string"},
    "retired_at": {"type": "string"},
    "supersedes": {"type": "string"},  # id of the episodic row this replaces
    "run_receipt_id": {"type": "string"},
}

USER_NAMESPACE_SCHEMA: dict[
    str, str | AttributeSchemaConfigParam | AttributeSchemaDropParam
] = {
    "kind": {"type": "string", "filterable": True},
    "status": {"type": "string", "filterable": True},  # active, superseded
    "content": {"type": "string", "full_text_search": True},
    "tags": {"type": "[]string", "filterable": True},
    "supersedes": {"type": "string"},  # id of observation this replaces
    # AT-URIs backing this row. for observations: the post(s) that justify it.
    # for interactions: [parent_uri, bot_post_uri]. empty is allowed but read
    # as lower-trust ("uncited"). DID + NSID + TID are extractable from the
    # URI itself, so author / kind / timestamp need no separate fields.
    "source_uris": {"type": "[]string"},
    "created_at": {"type": "string"},
    "updated_at": {"type": "string"},
}
