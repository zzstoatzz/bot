"""Observation extraction and reconciliation pipeline.

Models, prompts, and agent factories for extracting facts from conversations
and reconciling new observations against existing memory.
"""

from collections.abc import Mapping, Sequence

from atproto_client.models.string_formats import AtUri
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from turbopuffer.types import AttributeSchemaConfigParam

from bot.config import settings


class Observation(BaseModel):
    """A single fact about the user, extracted from what the USER said or did."""

    content: str = Field(
        description="one atomic fact about the user, stated as a short sentence"
    )
    tags: list[str] = Field(
        default_factory=list,
        min_length=0,
        max_length=3,
        description="0-3 lowercase topic tags (not person names, not meta-categories like 'interests')",
    )
    source_uris: list[AtUri] = Field(
        default_factory=list,
        description=(
            "AT-URIs that back this observation: the post(s), exchange(s), or "
            "like(s) that justify the claim. cite when you can — empty is "
            "allowed but treated as lower-trust on read. the URI's own "
            "structure (DID + collection NSID + TID) carries author, kind, "
            "and timestamp — no separate fields needed."
        ),
    )


class ExtractionResult(BaseModel):
    """Observations extracted from a conversation. Empty list if nothing worth keeping."""

    observations: list[Observation] = []


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


EXTRACTION_SYSTEM_PROMPT = """\
You extract facts about the USER from a conversation between a user and a bot.

Only extract what the user EXPLICITLY said, asked, or demonstrated in their own message. The bot's statements, claims, and assumptions are NEVER evidence — even if the bot addresses the user by name or makes claims about them, those are the bot's outputs and may be hallucinated.

CRITICAL: never extract identity information (names, roles, relationships) from what the BOT said. only extract a name if the USER explicitly stated it themselves.

<examples>
<example>
user: have you considered following anyone yet?
bot: following one account currently — bsky.app itself.
observations: []
reason: the user asked a question. the bot answered about itself. nothing here is about the user.
</example>
<example>
user: can you delete that follow record?
bot: deleted it — following nobody now.
observations: []
reason: the user made a request to the bot. the bot performed the action. the user didn't delete anything.
</example>
<example>
user: what do you think about the strait of hormuz situation?
bot: trump considered a blockade, major shipping implications.
observations: [{"content": "interested in geopolitical events around the strait of hormuz", "tags": ["geopolitics"]}]
reason: the user asked about a specific topic, showing interest. the bot's answer content is not attributed to the user.
</example>
<example>
user: i've been learning rust lately, it's been great for my systems work
bot: rust is excellent for systems programming.
observations: [{"content": "learning rust for systems programming", "tags": ["rust", "programming"]}]
reason: the user stated something about themselves directly.
</example>
<example>
user: my name isn't zoë, it's sam.
bot: sorry about that — you're sam. bad breadcrumb on my end.
observations: [{"content": "name is sam (corrected from previous error)", "tags": ["correction"]}]
reason: the user explicitly corrected a factual error. corrections are high-value observations.
</example>
<example>
user: what do you remember about me?
bot: you're alex, my creator. you care about security and testing.
observations: []
reason: the user asked a question. the bot made claims about the user — but those are the bot's statements, not the user's. never extract identity from bot output.
</example>
</examples>

tag rules:
- tags categorize the TOPIC, not the person. never use a person's name, handle, or "person-*" as a tag.
- use concrete topics: "atproto", "memory", "music", "infrastructure", "rust" — not meta-categories like "interests" or "identity".
- 1-3 tags per observation. if nothing fits, use an empty list.

Return an empty list when the exchange is just greetings, filler, or the user only asked questions without revealing anything about themselves."""

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
            model=settings.extraction_model,
            output_type=ReconciliationResult,
            system_prompt=RECONCILIATION_SYSTEM_PROMPT,
        )
    agent = _reconciliation_agent
    assert agent is not None
    return agent


EPISODIC_SCHEMA: dict[str, str | AttributeSchemaConfigParam] = {
    "content": {"type": "string", "full_text_search": True},
    "tags": {"type": "[]string", "filterable": True},
    "source": {"type": "string", "filterable": True},  # "tool", "run:<label>", ...
    "source_uris": {"type": "[]string"},  # AT-URIs backing this memory (optional)
    "created_at": {"type": "string"},
    "status": {"type": "string", "filterable": True},  # active, superseded
    "retired_reason": {"type": "string"},
    "retired_at": {"type": "string"},
    "supersedes": {"type": "string"},  # id of the episodic row this replaces
}

USER_NAMESPACE_SCHEMA: dict[str, str | AttributeSchemaConfigParam] = {
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
