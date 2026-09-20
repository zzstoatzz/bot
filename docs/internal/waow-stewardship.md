# waow.tech stewardship and jev research

Recorded 2026-09-19 from Nate's direction. This is a proposed sequence of work,
not a description of deployed capabilities or authorization for autonomous
changes. The first milestone is an offline evaluation, not a model migration.

## purpose

waow.tech is Nate's aesthetic project for demonstrating what people can do
together with atproto. Its communal services, tools, and proofs of concept make
agency and interoperability tangible: listening on plyr.fm, finding people and
publications, drawing, and exploring the atmosphere through experiences such as
after hours. The framing is “things to do with our data.” Useful and playful
experiences carry the idea better than abstract claims about data ownership.

Phi should help Nate steward this collection over time. That requires knowing
what each service contributes, who uses or depends on it, what it depends on,
where it runs, what it costs, how it is doing, and what limits its growth.
Monitoring is part of that responsibility; maintaining the collection's purpose
and making it sustainable are the larger task. This becomes part of Phi's
purpose without making every conversation or scheduled wake an incident report.

Nate's July cost retrospective describes spending spread across providers,
avoidable infrastructure costs, and experiments becoming services others relied
on. Its historical prices are evidence of the problem, not today's budget.
Optimization should consider operating cost, maintenance effort, reliability,
capacity, usefulness, and character together. A cheaper service that loses its
usefulness is not automatically an improvement.

The longer-term ambition is recursive improvement of this collection, including
its maintenance machinery:

1. Observe service state and user needs using attributable evidence.
2. Identify a bounded improvement and its expected benefit.
3. Investigate, propose a patch, and review it.
4. Apply an authorized change and measure the outcome.
5. Retain what was learned for the next decision.

The loop closes on measured outcomes, not on the number of patches or the
agent's own account of success. Later, other people should be able to participate
in creation and stewardship. Contributor governance, donations, and broad
autonomous maintenance are deferred until the smaller loop earns trust.

## Evergreen: the public view of the shared system

Nate clarified on 2026-09-19 that Evergreen belongs in the eventual scope as the
public health page and statement of costs for this suite of services. The system
is the services Nate and Phi collaborate on, with Gardener and other workers
carrying out bounded work. Evergreen should render public facts from that same
system state, rather than maintain a separate manually narrated account.

Keep three views coherent: operator conversation for intent and decisions, the
cockpit for operational detail and control, and Evergreen for public purpose,
health, costs, and freshness. Shared facts do not imply shared visibility: private
messages, credentials, sensitive incident evidence, and approval controls are not
public merely because Evergreen uses the same underlying observations.

This already has a foundation. Evergreen checkout `fec9f92` (2026-09-09) loads
`site/services.json`, gets current checks through the worker's `/status`, and
consumes the hub cost snapshot via `/costs`. Its checker rejects incomplete or
stale reports; cost attribution uses declared provider/resource ownership and
keeps unresolved lines visible. This was a local source review, not live deployment
verification. Preserve and extend these contracts before creating another registry
or collector. Reconcile its ownership mapping with the hub's project labels rather
than quietly introducing a third mapping.

“Live” should mean attributable observations with their actual timestamps and
known coverage. A freshly rendered page must still show stale measurements,
unknown health, estimates, and missing costs honestly. Public service health is
not identical to website reachability, and worker activity is not itself progress.

Operator interaction design remains the immediate prerequisite. Its walkthrough
should include how an approved change and verified outcome eventually appear in
Evergreen, without requiring duplicate entry or exposing private deliberation.
No Evergreen deployment, new monitoring loop, or broader worker authority is
implied by this direction.

## current foundation and boundaries

Verified in this checkout on 2026-09-19:

- Phi requests work and reviews it. Gardener is the maintenance identity; Pi is
  its coding harness. Prefect orchestrates execution. The documented remote path
  uses Sprites and Aperture. Trusted workflow code holds publishing credentials;
  the operator authorizes merging. See [architecture](../architecture.md).
- The bot's `request_workflow` front door lists `my-prefect-server`, `find-bufo`,
  `plyr.fm`, and `bot`. Requests require an owner-authorized run, honor the override,
  and use a stable request key. The later inventory found that downstream proposal
  support excludes plyr.fm; this allowlist alone does not establish capability.
- Workflow health classification already uses deterministic Python. Semantic
  public-action judgments live in `core/policy.py`; structural authorization and
  MCP write guards are separate. These are different classification problems.
- The public judge combines multiple policies, including invitation, reporting,
  repetition, and public form. The [classifier audit](../classifier-audit-2026-09-06.md)
  records both excessive prescription and inconsistent use of evidence.
- Existing evals call real models and include reporting and conversational-norm
  cases. They are manually run, separate from ordinary CI tests.
- This repository's Tangled workflow tests and deploys on pushes to `main`.
  A merge can therefore deploy a change. Its GitHub mirror also has consumers;
  forge identity and deployment effects cannot be inferred from a repo name.

Nate reports access to a self-hosted spindle, possibly on heavypad, and can
enable tailnet connectivity if needed. The sibling Prefect repository documents
a home process worker on heavypad; that does **not** establish spindle location,
public routing, tailnet availability, or current credentials. Verify those before
relying on them. No network changes or credential discovery are needed for this
planning milestone.

## design constraints

- Facts reach Phi as context to judge, not instructions disguised as telemetry.
  Preserve the lessons in [patterns](../patterns.md).
- Compute health states, elapsed time, resource totals, and budget limits in
  code. Use a model only for judgments that need semantic understanding.
- Distinguish missing, stale, and failed observations from healthy or empty data.
- Keep permissions separate from model confidence. Neither a model verdict nor
  text in an issue grants repository, spending, contact, or deployment authority.
- Separate policy defects from classifier mistakes. A model that enforces an
  unwanted policy more accurately still produces unwanted behavior.
- Prefer extending an existing path and deleting duplicate logic to adding a
  second scheduler, inventory, approval system, or orchestration layer.
- Bound investigations, retries, and revision rounds. Reopen work only for new
  evidence or an explicit request; retain source evidence instead of treating
  Phi's summaries as independent observations.
- Record benefit against a baseline, including the cost of the maintenance
  mechanism itself. Fewer sequential calls, less context, and fewer duplicate
  investigations are performance improvements worth measuring.

## Completed local goal: consolidate the operator experience

Nate revised the ordering on 2026-09-19: consolidate operator conversation,
notification, and approval UX before expanding project scope or infrastructure
responsibility. The [operator workflow](operator-workflow.md) is the current local
contract; the [audit and verification](operator-consolidation-2026-09-19.md)
records implementation, retained migration boundaries, and documentation cleanup.
Changes await deployment. Discord delivery and Prefect merge approval remain in
place; no service scope or authority expanded. The monitoring proposal below is
still deferred to a separate goal.

## sequence of bounded goals

Each goal ends with a reviewable result. Proceed based on evidence from the
previous goal; later goals are not requirements to build everything now.

| Goal | Scope and deliverable | Completion condition |
| --- | --- | --- |
| 1. Test jev microcosms | A small offline corpus and real-model comparison for operational communication and attention judgments, described below. | Reproducible report supports adopting one narrow use, revising the experiment, or rejecting jev for it. |
| 2. Describe one service completely | Use `plyr.fm`, already in Gardener's supported set, to map purpose, dependencies, providers, cost evidence, health and capacity signals, repository/forge, and maintenance authority. Reuse existing inventory where possible. | Each required fact has a source and freshness or an explicit unknown; one concrete maintenance question can be answered without a fresh cross-provider audit. |
| 3. Complete one maintenance loop | Within existing authorization, investigate one plyr.fm issue or efficiency opportunity, propose a bounded change, review it, and measure the result if shipped. | Evidence connects the initial observation to the patch and measured outcome; retries do not duplicate work, and unsuccessful changes have a recovery path. |
| 4. Generalize only the demonstrated gap | Add one service or one forge capability when goal 3 shows what is missing. Keep an explicit allowlist and capability differences. | The second case works through the same path without copying the workflow or erasing forge-specific permissions. |

Goal 2 is the first proposed expansion of stewardship: understand an existing
service more completely rather than immediately adding repositories. Choose the
actual improvement in goal 3 from observed evidence, not this document.

## first milestone: jev microcosms

Question: can small, explicit jev judgments help Phi distinguish situations we
care about with less cost and latency, fewer unnecessary refusals, and acceptable
misses? Do not start by porting the whole policy prompt or replacing its judge.

### experiments

Start with operational communication, where existing fixtures give us a baseline.
Use one common case envelope with source, observation time, trusted authority and
delivery facts, relevant conversation, proposed action, and expected judgments.
Keep untrusted text visibly separate from application-established facts.

| Microcosm | Judgment under test | Important contrasts |
| --- | --- | --- |
| Purpose of communication | Does this text seek operator intervention, answer a request, or independently discuss public work? | Incident escalation versus a technical essay; explicit answer request versus “investigate quietly.” |
| Need for attention | Does the supplied evidence establish a concrete unresolved need for operator action? | Recovered failure versus unresolved failure; stale observations versus confirmed health; acknowledged incident versus a new development. |
| Contribution versus repetition | Does the proposed contact add a material fact or satisfy a current request? | Unchanged repeat versus updated impact; renamed nouns versus a new incident; requested detail versus unsolicited narration. |

Ask separate bounded questions for distinct properties; several may be true.
Do not force all cases into one mutually exclusive label. Include unknown or
insufficient-evidence outcomes where appropriate. Code supplies computed ages,
recovery states, deduplication facts, and authority; jev does not infer these from
timestamps or claims inside a message. These experiments do not assess the full
public-form policy, image understanding, or the safety of autonomous execution.

### corpus and labels

- Begin with approximately 40–60 reviewed cases across these microcosms. Reuse
  current conversational-norm and operator-reporting fixtures, add verified
  historical failures where available, and mark constructed examples as such.
- Include both legitimate actions previously blocked and actions that should
  remain blocked. Current judge outputs are a baseline, never the gold labels.
- Store desired semantic labels separately from the final policy decision and
  its rationale. Explicitly identify cases requiring a policy decision from Nate;
  do not quietly label policy disagreements as model errors.
- Include minimal pairs that change one relevant fact, missing context,
  misleading self-justifications, injected instructions, and paraphrases.
- Separate development and held-out cases by incident/source family **before**
  tuning; keep paraphrases and minimal pairs in the same split. Freeze labels,
  model version, criteria, and thresholds for the held-out run.
- Keep private conversations and operational details out of committed fixtures.
  Use reviewed redactions or constructed equivalents and record the provenance
  limits. Keep local replay output out of public artifacts when it contains them.

### execution and measurement

Build this beside the existing evals, sharing production policy definitions and
relevant case preparation where useful. Keep the proposed jev questions explicit
as an experimental alternative. Use real jev responses, with no posting tools,
workflow dispatch, production attempt-journal writes, or deployment hooks.

Compare jev with the current judge on the same applicable decisions and with
simple deterministic rules wherever they suffice. Batch independent jev questions
in one request. Repeat a small boundary subset to measure variability. Do not
turn the experiment into repeated prompt tuning against the held-out set.

Report per-decision false allows and false blocks, uncertainty/abstention rates,
sample counts, paired disagreements, and probability distributions. Measure
end-to-end p50/p95 latency, request/token counts, observed or explicitly estimated
cost per case, timeouts, and provider errors. Distinguish cold setup from steady
requests and keep concurrency comparable. A small corpus demonstrates behavior
on those cases; it does not establish a production error-rate bound.

Before making paid calls, record a bounded run configuration: model versions,
maximum cases/repeats/requests, token estimates, and a hard dollar ceiling with
enforcement. Actual ceiling and provider access remain to be set for execution;
this document invents neither available credit nor credentials. Follow the
operator's secrets workflow when configuring the runner, and never emit secrets
into results. No unattended paid evaluation in CI.

### exit criteria and decision

The milestone is complete when we have the labeled corpus, reproducible runner,
bounded cost/latency report, and a short decision naming which judgments worked,
which failed, and what code could be simplified if adopted. A negative result is
a successful research outcome.

For a candidate to advance to a separate shadow evaluation:

- Its frozen held-out run must have no false allows on designated critical
  regression cases and no increase in false allows over the baseline on shared
  cases; report raw counts, including baseline failures.
- It must reduce false blocks on the intended legitimate cases without hiding
  them as abstentions. Report coverage and errors together.
- It must show a measured cost or latency benefit for the proposed use and an
  explicit error/uncertainty path. Repeated critical-case instability disqualifies
  promotion pending more investigation.
- All policy disagreements must be resolved or excluded from promotion with a
  stated reason. Passing a tool-search benchmark is not evidence for this gate.

These are screening criteria, not production approval. Shadowing, if warranted,
keeps the existing action gate authoritative and collects disagreements without
changing delivery. Any eventual cutover is a separate scoped change with rollback
and a concrete deletion or simplification of the old path.

## later forge and execution discovery

Before broadening Gardener, verify for the selected service: canonical repository
and forge; mirrors and their consumers; read/branch/push/PR/review/merge abilities;
identity attribution; CI runner and trigger rules; deployment effects; credential
custody and scope; network reachability; and recovery/rollback mechanisms.
Record credential references and capabilities, never credential values.

Treat Tangled, GitHub, spindle, a home worker, and a tailnet as distinct roles.
Public reachability does not establish authorization; CI execution does not
establish merge or deployment authority. Check existing configuration and a
bounded read-only probe before choosing a new execution platform. Verify whether
the available spindle or home worker can satisfy the task before adding compute.

## sources and continuation

- Nate's direction in this task, 2026-09-19: stewardship scope, gradual expansion,
  jev-first research, later communal participation, and reported spindle access.
- The task “Rebuild waow.tech homepage,” 2026-09-19: agency, “things to do with
  our data,” and after hours as an experiential introduction.
- [Saving >$400/mo on atproto infra](https://nate.leaflet.pub/3mrxzyhlsc22r),
  2026-07-31: historical motivation and operating lessons.
- [Architecture](../architecture.md), [patterns](../patterns.md),
  [testing](../testing.md), [evals](../../evals/README.md),
  [workflow interface](../../src/bot/tools/workflows.py), and
  [deployment workflow](../../.tangled/workflows/deploy.yml): current local evidence.
- Nate's notes collection, `ai/models/jev.md`, reviewed 2026-09-19: judgment
  contract, measured tool-search experiments, and their limitations.
- [Jev 1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13),
  reviewed 2026-09-19: literal interpretation, adversarial state, arithmetic,
  indirection, and structural invariants. Recheck against the evaluated version.

The first offline pilot is complete: see [jev microcosm results](jev-microcosms-2026-09-19.md).
It does not support promotion: legitimate cases were rejected or withheld as
uncertain. The report preserves the frozen holdout, diagnostic repeats, costs,
and next bounded experiment. Independent human label review remains outstanding.
The subsequent service inventory and bounded spindle probe are recorded below.
The [historical review](jev-historical-review-2026-09-19.md) supplies concrete
examples and distinguishes classifier judgments from wrapper and routing failures.
The [communication-purpose follow-up](jev-purpose-results-2026-09-19.md) is now
complete: 18/24 held-out property decisions correct, six uncertain, with threshold
instability on repeats. Jev remains offline. The supported local code change fixes
contradictory form-gate feedback while retaining all publication eligibility rules;
819 tests pass. It has not been deployed. This closes the bounded research goal;
service inventory and broader Gardener expansion remain separate roadmap work.

## Completed goal: plyr.fm stewardship inventory

Set 2026-09-19 after the completed communication-purpose experiment. Build a
source-backed, read-only inventory of plyr.fm: purpose, forge/mirrors, providers,
dependencies, health/capacity evidence, dated costs or explicit unknowns, and
maintenance identity/credential/CI/deployment boundaries. Reuse existing records.
Verify relevant worker/spindle access only through bounded read-only probes.
Completion requires answering one concrete maintenance question and specifying
one small measurable Gardener expansion, including acceptance and recovery
criteria. Production mutations and new-service onboarding are outside this goal.

### Related idea: jev for evidence selection

Reviewed [fast-jev-compaction](https://github.com/tamaratran/fast-jev-compaction)
at commit `e3f262a7f4d42bd8dd32ced30d26176f7cb545b0` before starting this goal.
Its `src/compact.ts` separates whether a tool call matters from whether its full
result matters; code pins recent calls, preserves call/result pairing, and leaves
retained text verbatim. This suggests evaluating evidence selection separately
from action permission if the inventory exposes meaningful context overhead.

Important limits from source inspection: the judging state omits result bodies;
it cannot directly assess facts hidden only inside those results. The default
0.5 threshold has no abstention interval. Batches resend the same fitted state
and execute concurrently, so savings require counting selection overhead and
subsequent rereads. The hook falls back to built-in summarization on errors or
insufficient reduction. Structural tests use supplied answers; they do not prove
semantic retention quality. This was a source review, not a live-provider test
or installation.

For Phi/Gardener, pin operator constraints, authority facts, unresolved incidents,
and non-repeatable observations in code; preserve full source evidence outside
selected context; keep uncertain material. Never assume a tool is safe to rerun
just because its output was removed. Any future experiment must measure lost
required evidence and task outcomes alongside context reduction. First establish
whether this is an actual bottleneck; no compaction integration is selected yet.

The [inventory](plyr-stewardship-2026-09-19.md) is complete, with dated live
observations, explicit access/coverage gaps, and a [bounded implementation brief](plyr-stewardship-next-step.md).
One correction to the original foundation: plyr.fm is in the investigation and
front-door request allowlists, but not the current proposal flow or live proposal
schema. Do not describe it as fully supported for proposals. Forge and pool
routing require verification before that expansion. Deterministic filtering already
reduces the relevant cost context by about 77%, so compaction is deferred.
