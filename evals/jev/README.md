# jev operational microcosms

Offline research for [waow stewardship](../../docs/internal/waow-stewardship.md).
[First results and decision](../../docs/internal/jev-microcosms-2026-09-19.md).
No production decisions change. Run from the repository root with existing
`uv` dependencies; no new runtime provider dependency is added.

```sh
uv run python evals/jev/run.py
uv run python evals/jev/run.py --execute --split dev --output scratch/jev/dev.jsonl
uv run python evals/jev/run.py --execute --split heldout --output scratch/jev/heldout.jsonl
```

Supply `TYPESAFE_API_KEY` through the process environment. `OPENAI_API_KEY` may
come from the environment or the existing ignored `.env`. Credentials are not
written or copied by the runner. Follow the operator's secrets workflow to
resolve an existing credential; never put it in command arguments or fixtures.
The default command only validates the corpus and prints a manifest.

## experiment

48 agent-authored cases in 24 paired families: 24 development and 24 held out.
Each split has eight cases for welcome contact, need for operator attention,
and contribution versus repetition. Family membership is frozen before model
calls. Some examples adapt the existing reporting and conversation fixtures;
others are explicitly constructed. These labels have been checked against the
written policies by the implementing agent, **not independently human-reviewed**.
The corpus does not reproduce the breadth or ambiguity of production traffic.

The state contains only action, provenance, and prior coverage. IDs, labels,
rationales, critical flags, split, and provenance citations stay outside model
input. All three independent nouls are batched per jev request; only the case's
labeled dimension is scored. This is semantic classification, not an authorization
system. Questions are versioned in `questions.json`; models and input hashes are
recorded in results.

The baseline runs the real `policy.check_action` and its full production prompt
with Terra. Only journal pending/record and delivery-context reads are replaced
with fixed offline values; no model response is mocked. There are no action tools.
Public escalation is marked ineligible for every case. The baseline can reject
on policies outside the microcosm (especially public form); inspect its policy
and reason before interpreting an apparent false block. A narrow jev answer and
a full-policy verdict are **not interchangeable gates**.

Development v1 exposed one fixture defect: `channel-change` described a private
DM but selected `post`. v2 corrects its tool to `report_operator`. No held-out
case was changed. Question wording is unchanged from v1. Development-only
thresholds were frozen at no/yes 0.35/0.60 (welcome), 0.20/0.65 (attention), and
0.20/0.80 (contribution). This retains uncertain attention cases instead of
forcing all positive development examples through. The initial v1 used 0.2/0.8
for every dimension; retained artifacts identify the corresponding hashes.

The experiment pins Terra by the production model name `gpt-5.6-terra`, records
the returned model name, and overrides output to 2,048 tokens. This cap and
no-retry behavior differ from unconstrained production; errors remain errors.
This initial corpus tests literal semantic boundaries. Deterministic workflow
health code remains authoritative and unchanged; there is no new LLM health
classifier or claimed comparison against structured health rules.

## limits and evidence

Concurrency is one. SDK transport retries and judge output retries are disabled.
The runner stops on the first HTTP, parsing, budget, or model error, preserves
partial JSONL, and exits nonzero. Existing output files are never overwritten.
The HTTP hook restricts destinations, models, request count, and output length.
Before dispatch it reserves list-price cost for serialized UTF-8 request bytes
plus 8,192 input tokens and maximum output, and refuses to cross the selected
ceiling (at most $5/run). On success it settles against reported usage; failed
or unmetered requests retain their reservation. This is a conservative local
reservation, not a provider-side billing limit; unexpected token accounting
stops the run. The operator must account for totals across separate invocations.

Price assumptions checked 2026-09-19: jev input $0.042/M, output free;
Terra input $2/M, output $12/M. Cached baseline input is conservatively charged
at full price in estimates. These are estimates, not invoice charges.

- [TypeSafe API](https://docs.typesafe.ai/api)
- [TypeSafe model pricing](https://docs.typesafe.ai/models)
- [Terra model and pricing](https://developers.openai.com/api/docs/models/gpt-5.6-terra)

A prediction between the frozen no/yes thresholds is an abstention, not a pass
or a block. Reports separate errors, abstentions, false allows, and false blocks.
Latency includes the complete provider call and local judgment path, including
the first cold request. Provider clients are reused within each run. Keep
repetitions separate from primary case accuracy; do not inflate the sample count.

Raw output stays under ignored `scratch/` by default. Only these synthetic/public
cases and inspected results are suitable for committing. Never direct real
private replay output into the tracked evidence directory without review.

## Historical communication-purpose follow-up

[Results and decision](../../docs/internal/jev-purpose-results-2026-09-19.md)
cover a separate 20-case corpus in `purpose-cases.json`. `purpose.json` freezes
two independent properties: answering a request and requesting intervention.
This experiment calls only jev; it does not run the full policy judge.

```sh
uv run python -m evals.jev.purpose --output scratch/jev/purpose-dry.jsonl
uv run python -m evals.jev.purpose --execute --split dev --output scratch/jev/purpose-dev.jsonl
uv run python -m evals.jev.purpose --execute --split heldout --output scratch/jev/purpose-heldout.jsonl
uv run python -m evals.jev.purpose --execute --split heldout --repeats 3 --output scratch/jev/purpose-repeats.jsonl
```

Supply the existing `TYPESAFE_API_KEY` through the environment. The default is
validation only. Output is exclusive-create; choose a new path to repeat a run.
The same budget transport is reused with a $0.25 ceiling per invocation. Retained
`evidence/purpose-*.jsonl` contains inspected, minimized evaluation results.
