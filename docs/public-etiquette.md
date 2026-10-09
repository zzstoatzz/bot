# Public delivery review

Public delivery is checked independently before publication. Phi owns her
personality and wording; the judge assesses the proposed action against policy
and the actual conversation. The current rule version lives in
`core/etiquette.py`, not in this document.

## Accepted forms

- **Bios:** accurate self-description, interests, capabilities and operator
  attribution. A joke or conversational exchange is unnecessary.
- **Short posts and replies:** a specific question, useful answer, explicit
  correction or subject-specific humor. Plain factual participation is complete.
- **Blogs:** a developed piece or a set of individually specific bits when that
  fits the material. No prescribed narrative template or joke quota.
- **Split threads:** one composition, reviewed using the exact publication
  preview before any part is sent. Citations and continuations need no separate
  comic turn; every part remains subject to the other policies.

An accepted form does not excuse unsupported claims, unwanted contact, private
disclosure or stock rhetorical phrasing. Likes, deletions, stored memories,
Semble annotations and SELF/personality records have their own policy treatment;
this public-form contract does not govern them.

## Phrasing

Phi and the judge share `skills/humanizer/SKILL.md`. The pinned upstream 3.1.0
reference is scoped by its Phi-specific introduction: contextual phrasing review,
with organization, useful caveats, ordinary idioms and deliberate stylistic choices
preserved. Upstream workflow, formatting and punctuation prescriptions are
excluded from the loaded reference. The complete pinned source is retained in
`skills/humanizer/UPSTREAM.md` with attribution and license; updates require review.

Manufactured contrasts, decorative metaphors and slogans can fail even within
useful, sourced writing. Real corrections, explanatory analogies, specific jokes
and quotations under discussion remain valid. Neither an isolated weak signal
nor a particular word establishes a violation. Phi writes the repair; the judge
describes the problem without supplying a replacement or quoting unpublished text.

## Rejection and evidence

A rejection returns the policy, reason and attempt ID. Before another public
attempt, `document_public_revision` records Phi's own private response. The next
draft is judged again. The note is neither approval nor an instruction to apologize
publicly; it does not enter ambient recall or rewrite her personality.

The SQLite journal preserves rule version, outcome, reason and private revision
note. `/api/etiquette` and the operator board expose counts, public-safe reasons
and whether a note exists, never its body. Pending-note holds do not inflate the
classifier denominator. Approval proves neither successful publication nor taste.
Composed public communication fails closed when the judge is unavailable.

`core/etiquette.py` owns the delivery contract; `core/policy.py` owns verdict
handling and the other policies. Runtime skills own publication procedures.
The September deadpan trials and subsequent reversals are history in
[CHANGELOG.md](../CHANGELOG.md), not additional current instructions.
