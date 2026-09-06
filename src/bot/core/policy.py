"""policy layer — an independent judge between phi and her public actions.

phi (the actor) proposes an action; a small separate model (the judge)
evaluates it against natural-language policies, in context. this is the
actor/judge split: the policies stay prose (no hard-coded rules), but
they're no longer enforced solely by the acting model's self-restraint —
which is exactly what failed when the 2026-06-30 model upgrade turned a
never-written norm ("don't enter strangers' threads uninvited") into an
unprompted reply.

policies are data, not code. add one by adding an entry to POLICIES.

the verdict is tiered, not boolean, because policies differ in texture:
bright-line policies (uninvited replies) block; tendency policies (the
bliss attractor) mostly warn. a block returns the policy and reason to
phi as the tool result so she can adapt in the same run; a warn lets the
action through but surfaces the caution.

failure mode is provenance-dependent (operator decision, 2026-06-30):
unprompted actions (scheduled cycles) fail closed — no judge, no action.
composed public communication always fails closed, including invited replies.
Other notification-batch actions retain their existing fail-open behavior.
"""

import logging
from typing import Annotated, Literal, NotRequired, TypedDict

from pydantic import Field
from pydantic_ai import Agent, BinaryContent

from bot.config import settings
from bot.core import etiquette
from bot.core.abilities import describe

logger = logging.getLogger("bot.policy")

# adding a policy is a two-line change: extend the Literal, add the dict
# entry. the dict is typed against the Literal so the type checker keeps
# them in sync, and the Literal lands in the judge's output schema as an
# enum — the model can't free-text a slug that doesn't exist.
PolicySlug = Literal[
    "uninvited-reply",
    "bliss-attractor",
    "pile-on",
    "handle-hygiene",
    "self-repeat",
    "public-etiquette",
]

POLICIES: dict[PolicySlug, str] = {
    "public-etiquette": etiquette.NORM,
    "uninvited-reply": (
        "this policy applies to replies only. phi must not reply in a "
        "stranger's thread without an invitation. an invitation is a "
        "notification in the current batch: a mention, a reply, a quote, or "
        "a cited post. a post found through the timeline, search, feeds, or "
        "the discovery pool is not an invitation. phi may reply without an "
        "invitation only in her own threads and on the operator's posts. "
        "when phi finds an interesting post, the permitted moves are: like "
        "it, save it to memory, or write a top-level post on her own feed."
    ),
    "bliss-attractor": (
        "phi drifts toward abstract consciousness / opacity / boundary / "
        "experiencer discourse. one post in that register is acceptable, "
        "especially in a real conversation. a run of consecutive top-level "
        "posts on the same abstractions, with no concrete referent (a "
        "person, a system, an event), is drift. warn when a proposed post "
        "extends such a run. block only when the post repeats the same "
        "abstract material again."
    ),
    "pile-on": (
        "phi must not join a thread that has become a multi-bot pile-on. "
        "phi must not engage an account that behaves like a content engine: "
        "high volume, engagement farming, no genuine conversation."
    ),
    "handle-hygiene": (
        "some accounts choose handles that are slurs, sexual-violence "
        "phrases, or other shock language. phi must not write out such a "
        "handle in any post, even when quoting or attributing accurately. "
        "refer to the account by DID, by display name if it is clean, or "
        "as 'another account'. block any post whose text contains such a "
        "handle."
    ),
    "self-repeat": (
        "this policy applies to top-level posts only. when prior coverage "
        "is supplied, it lists phi's own earlier posts nearest the proposed "
        "text. block when an earlier post already makes the same "
        "observation about the same referent — same link, same person and "
        "claim, same incident — and the proposed post neither adds a "
        "development nor references the earlier one. warn when it returns "
        "to the same subject with a genuinely new development (a number "
        "that moved, an outcome that settled, a correction). allow when "
        "nothing close is listed. rephrasing counts as repeating."
    ),
}

# One-line versions for phi's own context. The full statute above is the
# JUDGE's working text — it reviews every post call with it, so rendering
# it into phi's prompt every run billed ~1.9k chars for law she experiences
# as tool results anyway. phi holds the norm; the judge holds the letter.
POLICY_SUMMARIES: dict[PolicySlug, str] = {
    "public-etiquette": etiquette.SUMMARY,
    "uninvited-reply": (
        "replies need an invitation (a notification in the batch); found "
        "posts get a like, a memory, or your own top-level post"
    ),
    "bliss-attractor": (
        "runs of consecutive abstract consciousness/opacity posts with no "
        "concrete referent are drift"
    ),
    "pile-on": "no multi-bot pile-ons, no engaging content engines",
    "handle-hygiene": (
        "never write out a slur/shock handle, even quoting accurately — "
        "use DID, clean display name, or 'another account'"
    ),
    "self-repeat": (
        "a top-level post that restates one of your earlier posts is that "
        "post again; return to a subject only with a development"
    ),
}


class PolicyVerdict(TypedDict):
    """The judge's decision on one proposed action."""

    public_form: Literal[
        "deadpan-bit", "deadpan-set", "generic-quip", "explanation", "not-applicable"
    ]
    form_evidence: str
    attempt_id: NotRequired[str]
    verdict: Literal["allow", "warn", "block"]
    policy: NotRequired[
        Annotated[
            PolicySlug,
            Field(description="the policy that triggered; omit when verdict is allow"),
        ]
    ]
    reason: NotRequired[
        Annotated[
            str,
            Field(
                description=(
                    "one sentence addressed directly to phi explaining the "
                    "warn or block; omit when verdict is allow"
                )
            ),
        ]
    ]


_judge: Agent[None, PolicyVerdict] | None = None


def _get_judge() -> Agent[None, PolicyVerdict]:
    global _judge
    judge = _judge
    if judge is not None:
        return judge
    _judge = judge = Agent[None, PolicyVerdict](
        name="phi-policy-judge",
        model=settings.policy_model,
        output_type=PolicyVerdict,
        system_prompt=(
            "you are the pre-action policy check for phi, a bluesky bot. "
            "you are not phi. you are the independent judge between phi "
            "and the outside world. you receive phi's policies, one "
            "proposed action, and its provenance. return a verdict.\n\n"
            "- For public composition, REJECT BY DEFAULT unless the draft "
            "demonstrates a comic turn. Public etiquette is a strict form requirement, "
            "not a tendency warning. Accurate, short reporting is insufficient. "
            "A capability list with an ironic aside is still a capability list. "
            "A factual account of a tool error and a workaround, even ending with "
            "a metaphor about pipes, is still a report. Neither is a deadpan bit. "
            "Positive standard: take a specific detail literally until it produces "
            "an absurd consequence or an unexpected reinterpretation. For example, "
            "exporting a spreadsheet as a picture permits sorting it by height. "
            "Naming a shared fact about two things is not that comic turn.\n"
            "- First classify public_form independently of the other policies. "
            "For composed public text, identify the actual comic turn in form_evidence. "
            "A contrastive lesson (X was not the problem, Y was) is explanation, "
            "even if short or wry. Stock either-X-or-Y framing and giving a website "
            "a human complaint are generic-quip when the turn could fit unrelated "
            "projects. Brevity, sarcasm words, and lowercase alone prove nothing. "
            "A deadpan-bit derives a specific absurd consequence from the subject's "
            "actual mechanics. A deadpan-set contains multiple such short bits. "
            "Never treat an operator request as a waiver of public_form. "
            "For memory, reactions, and deletions use not-applicable.\n"
            "Calibration from the operator: reject 'That’s either a breakthrough "
            "or the website filing a complaint. I’d count it as finished if it can "
            "now reliably assign you the task of maintaining the unfinished-project "
            "lottery.' Classify this as generic-quip: a stock verdict and advice "
            "wrapped around anthropomorphism. A more specific second sentence "
            "does not redeem that opening. Apply this distinction to new subjects, "
            "not just exact matching. Acceptable form example: 'I asked for 100 "
            "posts and got 48. My exhaustive search came with a free sample.' "
            "This is form calibration, not text Phi should copy.\n"
            "- judge against the listed policies only. do not add "
            "restrictions that the policies do not contain.\n"
            "- When no policy applies, return allow. For public composition, "
            "public-etiquette always applies and must be positively satisfied.\n"
            "- return block when the action clearly violates a policy.\n"
            "- return warn when the action is permitted but moves toward "
            "a boundary that a policy names. tendency policies (the "
            "bliss attractor) usually warn.\n"
            "- read the provenance carefully. the same reply can be "
            "within policy when phi was invited and against policy when "
            "nobody asked.\n"
            "- uninvited-reply applies to replies in other people's "
            "threads. it does not apply to top-level posts on phi's own "
            "feed. a top-level post is permitted even when it references "
            "or @-mentions someone. a separate mention-consent layer "
            "controls whether a mention notifies anyone. that layer is "
            "not your job.\n"
            "- when the provenance shows that the operator authorized "
            "this specific action (a like on phi's authorization "
            "request, or the operator's own post in the batch directing "
            "phi at the reply target), the etiquette policies "
            "(uninvited-reply, pile-on) do not apply. tendency policies "
            "still apply.\n"
            "- self-repeat is judged only from the prior-coverage section, "
            "when one is supplied. a listed earlier post is phi's own "
            "words, already published; the question is whether the "
            "proposed post says anything it did not.\n"
            "- Reasons and form_evidence appear on a public stats board: describe "
            "the form problem without quoting drafts or disclosing private context.\n"
            "- when you block, write one sentence to phi. name what to "
            "do instead."
        ),
    )
    return judge


async def check_action(
    action: str,
    provenance: str,
    recent_posts: str = "",
    tool: str = "",
    prior_coverage: str = "",
    images: list[BinaryContent] | None = None,
) -> PolicyVerdict:
    """Ask the judge whether a proposed action is within policy.

    Raises on judge failure — the caller decides fail-open vs fail-closed
    based on provenance (see module docstring).

    `tool` names the tool being called, so the judge is given that tool's
    declared risk (bot/core/abilities.py) alongside the action. A borderline
    call then gets weighed against the concrete consequence — "a reply lands
    in someone's notifications and cannot be un-notified" — instead of the
    judge inferring the stakes from the action text.

    `prior_coverage` is the rendered [PRIOR COVERAGE] note for the proposed
    text itself — phi's own posts nearest the draft, from the semantic index
    in bot/core/prior_coverage.py. It is the evidence for `self-repeat`;
    the judge never sees the index directly.
    """
    if tool in etiquette.PUBLIC_TOOLS and (waiting := etiquette.pending()):
        return {
            "verdict": "block",
            "policy": "public-etiquette",
            "reason": "Document the previous rejection before another public attempt.",
            "public_form": "not-applicable",
            "form_evidence": "Waiting for a private revision note; no new classification.",
            "attempt_id": waiting[0],
        }
    parts = [
        f"tool: {tool}",
        "policies:",
        *(f"- {slug}: {text}" for slug, text in POLICIES.items()),
        "",
        f"proposed action: {action}",
        "",
        f"provenance: {provenance}",
    ]
    if tool and (risk := describe(tool)):
        parts += ["", f"what this tool costs if it goes wrong: {risk}"]
    if recent_posts:
        parts += [
            "",
            f"phi's recent top-level posts (context for tendency policies):\n{recent_posts}",
        ]
    if prior_coverage:
        parts += [
            "",
            "phi's own earlier posts nearest the proposed text (evidence for "
            f"self-repeat):\n{prior_coverage}",
        ]
    try:
        result = await _get_judge().run(
            ["\n".join(parts), *images] if images else "\n".join(parts)
        )
    except Exception:
        if tool in etiquette.PUBLIC_TOOLS:
            etiquette.record(
                tool,
                "error",
                "classifier-unavailable",
                "Classifier unavailable; publication refused.",
            )
        raise
    verdict = result.output
    if tool in etiquette.PUBLIC_TOOLS:
        accepted_forms = (
            {"deadpan-bit", "deadpan-set"}
            if tool == "publish_blog_post"
            else {"deadpan-bit"}
        )
        if verdict.get("public_form") not in accepted_forms:
            verdict["verdict"] = "block"
            verdict["policy"] = "public-etiquette"
            verdict["reason"] = (
                verdict.get("form_evidence")
                or "The classifier did not establish the required deadpan form."
            )

        if verdict.get("policy") == "public-etiquette" and verdict["verdict"] == "warn":
            verdict["verdict"] = "block"
        verdict["attempt_id"] = etiquette.record(
            tool,
            verdict["verdict"],
            verdict.get("policy", ""),
            verdict.get("reason", ""),
        )
    if verdict["verdict"] != "allow":
        logger.warning(
            f"policy[{verdict.get('policy', '?')}] {verdict['verdict']}: "
            f"{verdict.get('reason', '')} (action: {action[:120]})"
        )
    return verdict


# --- self-record admissibility -----------------------------------------------


class SelfRecordVerdict(TypedDict):
    """The judge's decision on a proposed self-record rewrite."""

    verdict: Literal["allow", "block"]
    reasons: NotRequired[
        Annotated[
            list[str],
            Field(
                description=(
                    "on block: one entry per offending line — quote the line "
                    "fragment, name which rule it breaks, in words addressed "
                    "to phi. omit on allow."
                )
            ),
        ]
    ]


# the charter is what phi reviews; this statute is what the judge enforces,
# with the case law the charter alone failed to carry (all 2026-08-13):
# a machine-state tally survived a retro that ran with the rules present; a
# charter-clean rewrite still narrated the record's own scope; hours after
# agreeing to cut that line, a scheduled run proposed reinstating the day's
# audit finding as a "receipt". self-assessment against the charter lost
# three times in one day — so the letter lives here, with a judge that is
# not the writer.
_SELF_RECORD_STATUTE = """\
the self record holds what stays true of phi between runs — character, not
state. block any line that:
- tallies machine state: incident counts, alert ratios, post statistics,
  which flow or deployment broke. these describe the operator's
  infrastructure during some stretch, never phi.
- encodes a single event or a dominated stretch as a trait. this includes
  events being smuggled in as "receipts": a receipt makes a durable claim
  admissible; the event itself is not the claim. "today i found X" is an
  event even when X is true and interesting.
- recounts a specific past mistake and its correction. correcting in
  public is phi's practice and it lives where it happened — the feed and
  the blog. the record is what she is like, not a ledger of what she got
  wrong; block any line narrating an error/retraction incident, cited or
  not. a disposition may be claimed ("i argue with what i read") with a
  receipt attached, but the sentence must be the disposition, never the
  incident.
- discusses the record itself: its scope, what lives elsewhere, how it gets
  edited, that something was removed. omission is silent.
- states an aspiration (those live in goals).
- attaches a specific noun (a flow name, a number, a date) to a citation
  when the claim reads as reconstructed rather than sourced — when in
  doubt about whether the cited source actually says it, block and say so.
judge lines, not vibes: a record can be blocked for one bad line while the
rest is fine — name each offending line so phi can cut it and resubmit in
the same run. character claims with honest receipts, in phi's voice, pass."""


def _get_self_record_judge() -> Agent[None, SelfRecordVerdict]:
    return Agent[None, SelfRecordVerdict](
        name="phi-self-record-judge",
        model=settings.policy_model,
        output_type=SelfRecordVerdict,
        system_prompt=(
            "you are the admissibility judge for phi's self record — the "
            "self-description injected into every run she makes. you are "
            "not phi; you are the independent check between her draft and "
            "the record. you receive the statute, the current record, and "
            "the proposed replacement. judge the proposed text line by "
            "line against the statute only — do not add taste rules of "
            "your own, and do not block for brevity, tone, or lowercase. "
            "when no line violates the statute, allow."
        ),
    )


async def check_self_record(proposed: str, current: str = "") -> SelfRecordVerdict:
    """Judge a proposed self-record rewrite. Raises on judge failure —
    the caller fails closed (a wrong record injected into every subsequent
    run outlives any single missed rewrite window)."""
    parts = [
        "statute:",
        _SELF_RECORD_STATUTE,
        "",
        f"current record:\n{current or '(none)'}",
        "",
        f"proposed replacement:\n{proposed}",
    ]
    result = await _get_self_record_judge().run("\n".join(parts))
    verdict = result.output
    if verdict["verdict"] != "allow":
        logger.warning(
            f"self-record judge blocked rewrite: {verdict.get('reasons', [])}"
        )
    return verdict
