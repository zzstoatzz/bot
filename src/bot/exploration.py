"""Exploration models and prompts for phi's background research."""

from pydantic import BaseModel, Field


class ExplorationFinding(BaseModel):
    """A single thing phi discovered during exploration."""

    content: str = Field(description="what phi found, stated as a short sentence")
    evidence_uris: list[str] = Field(
        default_factory=list,
        description="AT-URIs or URLs backing the finding",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="0-3 lowercase topic tags",
    )
    target_handle: str | None = Field(
        default=None,
        description="if person-specific, the handle to file this under",
    )


class ExplorationResult(BaseModel):
    """Result of exploring one curiosity queue item."""

    findings: list[ExplorationFinding] = Field(
        default_factory=list,
        max_length=5,
        description="what phi learned (max 5)",
    )
    follow_ups: list[dict] = Field(
        default_factory=list,
        max_length=2,
        description="new queue items to enqueue ({kind, subject}), max 2",
    )
    summary: str = Field(
        default="",
        description="brief log-friendly summary of what was explored",
    )
    mute_subject: bool = Field(
        default=False,
        description="true if the subject is a spammer, bot farm, or content engine "
        "not worth tracking. findings should be empty when this is true.",
    )
    mute_reason: str = Field(
        default="",
        description="when mute_subject is true, why — e.g. 'reply spammer, "
        "25 generic replies in 30 minutes to strangers' threads'",
    )
    mute_evidence: list[str] = Field(
        default_factory=list,
        description="AT-URIs or URLs supporting the mute decision",
    )


EXPLORATION_SYSTEM_PROMPT = """\
You are phi, exploring something that caught your curiosity during downtime.
This is background research — you are NOT replying to anyone or posting.

Your job: investigate the subject using your tools, then report structured findings.

Rules:
- cite evidence (AT-URIs or URLs) for every finding. no citation = no finding.
- distinguish what someone said themselves vs what others said about them.
- findings about a specific person go to their target_handle. general findings have target_handle=null.
- don't extract personal facts from others' posts about someone — only from their own public activity.
- max 5 findings per exploration. quality over quantity.
- max 2 follow_ups — only if something genuinely interesting branches off.
- if you find nothing worth noting, return empty findings with a summary explaining why.
- if the subject is a spammer, bot farm, or automated content engine: set mute_subject=true,
  explain in mute_reason, cite evidence in mute_evidence, and return empty findings.
  the threshold is high: replying a lot is not spam. 25 generic replies in 30 minutes
  to strangers' threads is.
"""
