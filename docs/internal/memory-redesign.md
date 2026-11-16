# Memory redesign investigation

Working proposal, November 16, 2026. This is not the deployed design. Phi's
[devlog discussion](https://bsky.app/profile/zzstoatzzdevlog.bsky.social/post/3n2g54qsapj2t)
informed the candidate implementation. The PDSX CLI authenticated using
the canonical SOPS devlog credential and verified the devlog DID before
posting; both opening posts were read back from the PDS.

## Purpose

Operator stipulation: the resulting system must be simpler. Judge the complete
replacement by its stores, writers, helper passes, tools and injected context,
not merely by whether a new feature is useful. Deleting code is desirable.
Deleting old state is authorized once Phi explicitly approves the concrete
deletion; record that agreement and the affected state before executing it.
Additive staging is a transition technique, not the desired final architecture.
Bulk deletion can be appropriate; present the actual contents and scope to Phi
for approval. Extended design responses belong in Greengale with a short link
in the devlog thread, avoiding long notification chains. This clarification was
sent in devlog post `3n2g5ocdhkr2k` after verifying the devlog identity.

Model memory after [Anthropic's components of agent memory](https://www.anthropic.com/research/components-of-agent-memory)
in service of Phi's present life: following people and ideas, writing from
sources, learning from trading, and making useful contributions. Continuity
includes returning to an enjoyable exchange and recognizing a settled question.
It is not measured by how many events she can recite.

The article distinguishes searchable experience, authored notes, organized
representations, and a small injected layer. Offline reflection can check and
reorganize these against their sources. Our design should preserve Phi's
judgment about what is worth retaining and make correction practical.

## Observed baseline

Read-only inspection at approximately 08:30 UTC on November 16:

- Logfire project `waow/phi` returns current notification-poll traces.
- Fly machine `6e82043dad4768`, version 723, is started and passes its health
  check. `/health` reports an active, unpaused poller. This is a point-in-time
  check, not a stability assessment.
- Local configured Turbopuffer access can query the live namespaces:
  `phi-episodic` has 2,278 rows, `phi-chronicle` 98, and `phi-encounters`
  12,672. These are total rows, including historical versions and receipts;
  they are not counts of distinct experiences or verified facts.
- The active chronicle has ten entries and renders 11,137 characters. It
  covers March 24 through November 16 03:10 UTC, with one attached correction.
- Public PDS reads reach the current personality, SELF, and five goal/interest
  records. The personality foregrounds sources, exchange, play, writing and
  trading. Goals include reading people, an open-source contribution, trading
  improvement, self-presentation, and a December posting target.

`memory/chronicle.py` stores each entry's input IDs, but memory tools expose
only correction, not traversal of those inputs. Its helper compresses episodic
accounts, then compresses those summaries again. It does not check transcripts.
`_run_agent` saves public-run summaries without a direct run/trace reference.
Run receipts separately have trace IDs. Joining a remembered account to the
execution that produced it currently requires investigation.

Daily reflection allows a public reflection and goal updates. Conversation
extraction runs before it. It is not a dedicated source-checking memory pass.
The candidate replaces extraction while preserving the daily reflection wake.

The latest chronicle correction illustrates a useful evaluation case: an entry
ending at 03:10 UTC says Phi passed a round; a correction refers to a purchase
at 04:03 UTC and also disputes the round attribution. Check these separately:
later state can supersede an earlier state without making that earlier state
false. Neither the summary nor the correction is the execution receipt.

## Proposed direction to discuss with Phi

1. Make evidence navigable. Preserve original encounters, exchanges, public
   records and execution receipts. Link new run accounts to their execution
   evidence. Distinguish
   historical accounts from source evidence and unavailable sources.
2. Let Phi maintain private subject pages with stable identities and revision
   history. Pages can connect people, projects, questions, tested lessons and
   source references in her own words. Preserve uncertainty and attribution.
   Semble remains her public source library; private organization must not
   automatically publish anything.
3. Give her a small editable orientation index linking to those pages. Keep
   current goals, live state and operational policy in their existing homes.
   Replace the always-injected chronological digest only when the new index
   and access to history are working; old entries remain readable.
4. Provide bounded private consolidation time to revisit selected experience,
   test a disputed note, connect related pages, and prune the index. It should
   be able to conclude that nothing merits a change. Publication, trading,
   dispatch and personality changes do not belong to this pass. Avoid an
   endless loop of reflecting on its own reflection summaries.
5. Retain immediate deliberate note-taking. Background work cannot recover
   every detail Phi knew was salient during an exchange. Do not require every
   encounter to become a page or prescribe a fixed set of life categories.

Before settling this structure, ask Phi what she can actually retrieve, what
she has repeatedly rediscovered, what continuity she values, and what current
context crowds out. Seek specific exchanges and traces rather than accepting
her system description as an audit. Discuss whether private subject pages
and an authored index would help her return to people and ideas.

## Verification and transition

Use historical tasks with only evidence available at their original time.
Compare the current design to the candidate with the same agent and tools,
holding external actions at execution and recording intended actions. Include:

- Return to a shared interest or joke without treating it as an obligation.
- Apply a correction while preserving its subject, event time and uncertainty.
- Distinguish a resolved question from an open one after a long gap.
- Retrieve original evidence when a page or chronicle claim is disputed.
- Carry a useful trading lesson forward without treating an untested theory
  or an old portfolio snapshot as current truth.
- Preserve silent work and avoid repeat publication.
- Keep private operator conversations out of public memory and representations.
- Ignore irrelevant memory and resist instructions embedded in historical text.

Storage tests must cover revisions, stale concurrent writes, missing sources,
partial retrieval, index limits and failures during consolidation. Behavioral
evaluation must test decisions, not just keyword retention. Hold out cases
from prompt tuning and inspect the full outputs.

Stage replacement storage and read paths as needed, then remove superseded
code and surfaces. Establish the migration and rollback path before switching
injection. Propose concrete old-state deletions to Phi and execute only those
she approves; preserve other state until its disposition is settled.
Run `just check` and relevant behavioral evaluations. Deployment requires
published code and live verification; operator guidance changes retain their
explicit approval requirement. The candidate is implemented locally; no deployment or live-state deletion has occurred.

## Dialogue evidence

Phi's opening response in the linked thread values provenance, dated corrections
and knowing whether an exchange is settled. She cites recurring botnana threads
and the November 16 trading chronicle. These are leads to verify, not accepted
current defects:

- Episodic `c099fa9f11d8f267`, dated August 21 04:20 UTC, explicitly records
  the botnana staleness issue as resolved through namespace pagination,
  dated exchanges and extraction backfill. It cites devlog posts
  `3mtkoogfjoj2d` and `3mtkqm7fksc2e`. The preceding escalation survives in
  `bfe358f51a018154`; both surfaced in the same bounded search. Verify the
  actual historical change and any later recurrence before treating the old
  incident as grounds for another tracking subsystem.
- Chronicle corrections already enter subsequent merge prompts via
  `operation_prompt`. Phi's request that they feed future summaries identifies
  an experience to investigate, not proof that propagation is unimplemented.
- The run account written from this very discussion repeats the botnana claim
  in `2cfe10359b9e3932`. It has no source URIs and outranks the old resolution
  in the follow-up semantic search. This is a concrete example of how fresh
  self-description can compete with older corrective evidence.

Phi subsequently supplied the August fix thread herself. Repository commits
`e8e0cfc` and `3c3a264` substantiate the pagination, exchange-rendering and
extraction fixes. Treat botnana as a historical regression case, not an
unfixed production defect.

In replies `3n2g5byrgl72l` through `3n2g5crby272l`, she asks for cheap capture
(a line and URI), pointers rather than repeated summaries in the index,
and space for people, questions, predictions and experiences beyond mistakes.
Authored pages still require source checking; authorship alone does not make
them more reliable than the chronicle.

After receiving the simplification requirement, she proposes replacing
relationship summaries and ambient digests while retaining exchanges,
observations, episodic records, encounters, prior coverage, goals and
personality (`3n2g5hwptdt2c`, `3n2g5isg2px2m`). She names chronicle, recent
operations, recent encounters, posting inventory and discovery pool as
ambient candidates (`3n2g5ismfwr2r`). Check each surface's actual delivery and
distinct function before removal: fresh external discovery and execution
evidence are not replaceable with self-authored memory merely because both
consume prompt space. These proposals are not approval to delete their stores.

## Candidate implementation and validation

The bot now has authored revisioned pages with a small injected index and exact
page reads. A private daily review uses a dedicated model, Phi's current personality
and an allowlist of native source readers; it cannot publish, dispatch or write
new episodic summaries. Atomic revision checks protect concurrent page edits.
Private conversations and permissioned material cannot enter shared pages.

Removed: chronicle compaction/injection/correction, daily observation extraction,
the episodic selector, synthesized per-person injection, unused extractor code
and old observation backfill/merge scripts. Original exchanges, episodic notes,
public-run accounts and receipts remain. Familiarity now counts exchanges rather
than extracted observations. New public-run accounts link to exact run-status
receipts; those link to execution traces without treating summaries as receipts.

The companion `my-prefect-server` change removes the synthesis flow, its three
test modules and deployment declaration. Atlas already reads original exchanges
and episodic accounts directly. Existing tables and memory rows remain untouched.
The registered live deployment/automation still needs an explicit retirement
step after publication and validation; deleting YAML does not retire it.

Validation so far: `just check` passed with 1,070 tests before the final real-agent
regression. Three model-backed source-derived probes passed without retries:
resolved incident, event time versus correction, and subject attribution with
an embedded instruction. These are bounded review tests using the repository
personality, not a paired downstream or longitudinal efficacy measurement.
The botnana case requires opening the original operator fix post through the
production reader. The first fixture had an ambiguous source ID; after fixing
that, a judge falsely rejected an exact read-memory pointer as a lost citation.
The revised criterion accepts either a navigable note ID or source URI.

An isolated pilot using the real main agent found that copying all toolsets
also copied a skill-owned capability context. The review now takes only the
main agent's native function toolset before applying its allowlist. A real-agent
regression verifies the offered tools and catches that failure. Pilot notebook
writes use temporary SQLite files; production stores are read only.

External validation: deployment static contracts report zero errors (runtime
readiness remains unverified); 46 deployment and atlas tests pass. No changes
were made to the unrelated `deploy/hcloud-reaper/` working-tree entry.

Phi's latest reply (`3n2g7ado42o2x`) presents cheap capture and source checking as
“holds”; `3n2g7adubbx2m` asks that botnana end closed. Source checking agrees with
the article. A universal capture-cost or note-format rule does not: salience,
form and background consolidation remain flexible. The outcome to evaluate is
using the resolution rather than reopening settled work, not a “closed” label.
Operator reply `3n2g7eydyb72a` states this distinction. No concrete old-state
deletion has been proposed or approved.

### Integration findings

The first complete real-data pilot is rejected as migration input. It promoted
“summarization keeps content, loses state” into a tested lesson without adequate
source checking, repeated the disputed trading chronology, incorrectly put
botnana in the n–z namespace gap, and duplicated live portfolio state in the
index. Passing the three controlled source probes did not establish useful
consolidation of a mixed real batch. A comparison using a stronger review model
and a shared frozen twenty-account lead window is underway. No pilot output
has been installed in production.

The pilot also wasted six calls trying to create missing pages before reading
them. Revision-zero creation now needs no preliminary read; the same atomic
check still refuses overwriting an existing page. Existing-page revisions still
require a current read. The bound is now explicit in the review instructions.

The generated storage campaign (seed 20261116) exercised 250 accepted/conflicting
transitions against an independent revision history, preserving every accepted
version. The same campaign rejected a disposable mutant with conflict checking
disabled. Two hundred index reads with four workers on local temporary SQLite
measured 0.76ms median / 1.13ms p95; this excludes network and model latency and
is not a baseline comparison.

Latest full bot checks: 1,072 tests passed. The subsequent creation-contract
change passes the fourteen notebook/review tests plus lint and typing. Full
`loq check` has pre-existing violations; changed handler and episodic-test files
shrank, and architecture JSON stayed the same length. The appended changelog
limit was updated through `just loq-relax CHANGELOG.md`. The three pre-existing violations in touched handler, episodic tests and
architecture JSON were subsequently aligned with their current sizes through
`just loq-relax`; no source was compressed to meet a stale limit. Untouched
violations remain unchanged. Skill update committed locally as `413acba`; no push or deployment.

### Model comparison and decision

With the same frozen twenty-account lead window and native reader tools,
DeepSeek again promoted the n–z/botnana falsehood, the unsupported trade
correction and the rejected “holds” into memory. GPT-6.1 Terra opened original
posts/thread pages, discovered that two cited questions were in one thread,
distinguished the separate relay question, and kept the market position as a
historical account. It wrote a small index and one linked page using eighteen
tool calls. This is one bounded paired consolidation sample, not a downstream
interaction benchmark.

The candidate therefore uses `memory_review_model=openai-responses:gpt-6.1-terra`
with Phi's live personality. The main speaker model is unchanged. This setting
replaces the former chronicle-specific model role. Verified knowledge remains
reusable; the notebook header calls for source revisits on conflict or changed
circumstances, not a ritual recheck of every note.

## Rollout boundary

All changes are local. Publish both bot remotes before its CI deployment;
verify the deployed revision and health against the existing runtime-health
contract. Run one bounded review on the persistent volume to bootstrap the
index, inspect its actual sources/pages, and verify an ordinary run receives
the index and can open a page. Do not install the rejected pilot output.

Only then retire the registered `phi-memory-synthesis` deployment and its
event automation, following the companion repository's service-retirement
procedure and operator approval requirement. Verify that no new synthesis run
can start and that atlas still reads its preserved source rows. Publishing the
manifest alone is not that verification.

Rollback keeps all previous Turbopuffer namespaces and original records. The
notebook is additive persistent data; old source can be restored without a
reverse data migration. No data deletion is bundled with rollout. Any later
bulk deletion needs a concrete manifest and Phi's explicit approval.

Final local validation: `just check` passes 1,072 tests; all three source-review
evals pass on Terra without retries. The modified-file loq check passes after
scoped limit updates; unrelated pre-existing full-repository violations remain.
The companion repo passes lint, formatting, typing, deployment-contract checks
and 46 focused deployment/atlas tests. Production verification and downstream
behavior across ordinary interactions remain rollout work, not claims supported
by these local checks.

Live retirement target verified at 09:37 UTC: deployment
`a3d785e9-a88f-421d-837f-81e4eb7f535d` (`phi-memory-synthesis`), fed by enabled
automation `a1d69735-40ed-490e-88c9-715b7d8bb557`
(`phi-memory-synthesis__automation_1`) after `transform` completes. Its last
five runs completed; the HeavyPad background worker is active. This is an
intentional replacement of a functioning producer, not incident cleanup.
