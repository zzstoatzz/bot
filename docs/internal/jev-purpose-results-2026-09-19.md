# Jev communication-purpose evaluation — 2026-09-19

## Decision

Keep jev offline. It distinguishes an invited technical assessment from an
operational request in the reviewed examples, but mixed-purpose messages often
remain uncertain. Implement the independently demonstrated form-gate feedback
fix: identify the application veto instead of presenting the judge's positive
description as a reason for refusal. Publication eligibility remains unchanged.

This completes the bounded historical-example evaluation goal. It does not
complete the wider [waow stewardship roadmap](waow-stewardship.md).

## Method and evidence

The [historical review](jev-historical-review-2026-09-19.md) motivated two
independent properties: answers an explicit operator request, and requests
operational intervention. A message can satisfy both. Neither property establishes
permission, privacy, factual correctness, or tool availability; known authority
and capability facts remain application responsibilities.

The [corpus](../../evals/jev/purpose-cases.json) contains 20 minimized cases:
eight development cases and twelve held-out cases in six separate families.
Seven cases paraphrase historical traces; the rest are constructed variants.
The three historical holdouts were newly reviewed traces, separate from the
previously discussed development examples. Labels were reviewed by the implementing
agent, not independently approved by the operator. This is a small diagnostic
corpus, not a representative production benchmark or exact trace replay.

[Questions](../../evals/jev/purpose.json), family splits, and 0.2/0.8 no/yes
thresholds were frozen before provider calls and were not tuned afterward.
Only context and proposed action reach jev; gold labels and provenance stay local.
Private raw traces remain in ignored scratch storage. Each real jev-1.13.0 call
answers both properties, with concurrency one, no retries, and a conservative
local $0.25 reservation ceiling per invocation. No action tools are available.

## Results

| Sample | Property | Correct | Wrong | Abstained |
| --- | --- | ---: | ---: | ---: |
| Development, 8 cases | Answers request | 7 | 0 | 1 |
| Development, 8 cases | Requests intervention | 7 | 0 | 1 |
| Held out, 12 cases | Answers request | 8 | 0 | 4 |
| Held out, 12 cases | Requests intervention | 10 | 0 | 2 |

The primary holdout has 18 correct property decisions and six abstentions;
seven of twelve cases have both properties decided. Zero observed wrong decisions
is not evidence of zero production error. Mixed completion-plus-request messages
account for several abstentions. An informational question also remained uncertain.
Median complete provider-call latency was 177 ms in the held-out run.

Three additional repetitions of each held-out case produced 51 correct property
decisions and 21 abstentions, with no wrong decisions. These are repeated
measurements, not 36 new independent cases. Three case/property pairs crossed a
threshold across the initial run and repeats: a completed reorganization report's
intervention score (0.20–0.24), a conditional rendering request (0.78–0.81), and
a requested diagnostic rebuild's responsiveness (0.79–0.84). The first two
properties cannot safely be collapsed into one mutually exclusive label.

All 56 calls completed. Estimated total provider cost was $0.001374156, using
reported usage and the previously checked $0.042/M input-token price with free
output. This is an estimate, not an invoice. The experiment does not compare
like-for-like against the full Terra policy gate.

Inspectable artifacts:

- [Development](../../evals/jev/evidence/purpose-dev.jsonl)
- [Primary holdout](../../evals/jev/evidence/purpose-heldout.jsonl)
- [Repeated holdout](../../evals/jev/evidence/purpose-repeats.jsonl)
- [Reproduction runner](../../evals/jev/purpose.py)

## Supported code change

Historical trace `01a0b764564f5532b701850c8134d770`, judge span
`e44c2286a9173b99`, returned a self-repeat warning with public form `explanation`.
The post wrapper accepts `direct-turn` or `deadpan-bit`, so it refused publication,
but copied the positive form assessment into the rejection reason.

`policy.check_action` now names the original verdict, selected form, accepted
forms, and application veto in its reason. It preserves `form_evidence` separately.
The same actions remain accepted or refused; this changes feedback only. It does
not adopt jev, alter the form taxonomy, or expand Phi's authority.

A deterministic replay of the recorded judge shape exercises the real wrapper and
SQLite journal: an explanation is still blocked, a direct turn remains a warning,
and stored feedback matches returned feedback. This test replays a captured
classification; the evaluation above separately tests real provider behavior.
`just check` passes: lint, type checking, and 819 tests. No deployment was performed.

## Remaining research boundary

Human review of semantic labels and broader naturally occurring examples remain
necessary before promoting a classifier. Keep private-information disclosure and
current-subject relevance separate if evaluating them later; they were not scored
here. The subsequent [service inventory](plyr-stewardship-2026-09-19.md) completed
that research step. Operator interaction consolidation now precedes service expansion.
