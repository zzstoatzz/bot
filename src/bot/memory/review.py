"""Memory review — the distill/dream pass.

Runs with distance from the original conversations. Reviews recent
observations and decides what to keep, supersede, or promote to
public cosmik cards. Structurally matches Claude Code's /dream skill:
write-time is fast and might be wrong, review-time is slow and has distance.
"""

from pydantic import BaseModel, Field


class ObservationReview(BaseModel):
    """Review decision for a single observation."""

    action: str = Field(description="keep, supersede, or promote")
    reason: str = Field(description="why this action")
    # only for promote: what the public cosmik card should say
    card_title: str | None = Field(
        default=None, description="title for the cosmik card if promoting"
    )
    card_description: str | None = Field(
        default=None, description="description for the cosmik card if promoting"
    )


class ReviewResult(BaseModel):
    """Result of reviewing a batch of observations."""

    decisions: list[ObservationReview] = Field(default_factory=list)
    summary: str = Field(default="", description="brief summary of what was reviewed")


REVIEW_SYSTEM_PROMPT = """\
You are reviewing observations that were extracted from conversations earlier.
You have distance now — you weren't in the conversation, you're looking at
the extracted facts after the fact.

For each observation, decide:
- **keep**: the observation is accurate and worth retaining privately.
- **supersede**: the observation is stale, wrong, or redundant. it should
  be marked superseded so it stops appearing in context.
- **promote**: the observation captures something worth sharing publicly
  as a cosmik card on semble. provide a card_title and card_description
  that would make sense to someone discovering it on the network.

Guidelines:
- most observations should be kept. supersede only if clearly wrong or stale.
- promote rarely — only observations that have value beyond phi's own use.
  a fact about what someone works on is private. a pattern worth naming is public.
- if you're unsure, keep. the cost of keeping is low (slightly cluttered context).
  the cost of wrong supersession is losing real information.
"""
