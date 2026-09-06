# changelog

## 2026-09-05 — Let long-form writing develop

The standalone-bit blog contract produced a repetitive observation/punchline
rhythm. Replace it with whole-piece assessment: connected development, natural
pacing, and humor that can build or recur across plain passages. Short-post
rules and private storage remain separate. Version judgments as deadpan-v4.

## 2026-09-05 — Remove conflicting blog form guidance

The blog skill advertised essays and independently granted form choice while
public etiquette required a different delivery form. Keep publishing and source
checks in the skill, and let the current public etiquette own composition form.
Personality and private or library notes retain their existing scope.

## 2026-09-05 — Classify emitted thread parts

A permitted draft split into a joke and a source-only second post. Preview the
existing splitter and classify each emitted part before publishing any of it.
Rejections retain the same private-documentation requirement.

## 2026-09-05 — Preserve the bio on startup

The deadpan gate exposed conflicting bio instructions and repeated rejections
delayed startup. Retire the automatic bio-writing run, keep the current text
across deployments, and remove the tool’s requirement to list capabilities.
Phi can still choose to revise her bio through the classified native tool.

## 2026-09-05 — Tighten the public trial after false approvals

The live classifier approved a plain routing report and a capabilities-list
bio. Require positive evidence of a comic turn, defaulting to rejection for
public composition. Give the actor an explicit temporary stand-up direction.
Retain v1 outcomes and show each attempt’s rule version on the board.

## 2026-09-05 — Public etiquette trial

Nate authorized a hard deadpan form for public communication, separate from
private thought and memory. Extend the independent classifier with explicit
form judgments, fail closed for public text, require Phi-authored private
revision notes after rejection, and expose durable outcome counts and reasons
on the operator page. Rejected drafts and private note text stay off the board.
This is a trial of form; voice acceptance remains Nate’s judgment.

## 2026-09-05 — Closeout repairs

Bound market reads to 20 seconds so a stalled request cannot leave Refresh
disabled indefinitely. Retain previous data and expose the existing error state.
Make native blog publication respect the operator pause before any write.
Remove the blog skill’s prescribed essay shape so Phi chooses the form herself.
Record the system map and deferred work in the closeout document.

## 2026-09-05: Phi authors the live personality

Nate authorized direct personality revisions after repeated voice failures.
`write_personality` appends a full revision on Phi’s PDS; the next run reads it
in place of the repository seed. Previous revisions remain available. The
current run keeps its original instructions, and operational rules stay
separate. A runtime skill gives Phi the operator’s feedback and the limitations
of the isolated voice experiments. No voice improvement is presumed.

## 2026-09-05 — Keep cache estimates within their provider scope

Record provider identity alongside observed token counts. Withhold the existing
Anthropic cost estimate for other providers, mixed models, or legacy records
without provider identity; retain their measured reuse. Restrict Anthropic
collapse heuristics to Anthropic responses. The cockpit shows unavailable costs
explicitly, labels supported savings as estimates, and labels per-request total
input correctly instead of calling cached tokens full-price input.

## 2026-09-05 — Exclude superseded user accounts from search

Scoped and current-author memory search returned replaced observations as ordinary
results, unlike episodic search. Exclude records explicitly marked superseded
from those results while retaining legacy records without status. Historical
records remain stored. Candidate limits and ranking are unchanged, so a search
can return fewer results when its candidate pool includes superseded records.

## 2026-09-05 — Retain the existing account when a save adds no information

The exact-wording path converted a reconciler NOOP into UPDATE. A brief Ali
regression note consequently archived the detailed correction, despite the
reconciler finding no new information. Save distinct submitted wording as ADD
in that case, preserving both accounts for retrieval. Genuine updates still
create successor versions; identical redundant wording remains a NOOP.

## 2026-09-05 — Separate music history from capability

Remove the unsupported claim that Phi makes music from her personality. Nate
placed older music records under the account; record ownership did not establish
that Phi composed them. Preserve his explanation in the account lore, attributed
and dated, without assigning Phi a future musical ambition.

## 2026-09-05 — Retain generated images before publication

The first live image-reply test hit a PDS limitation: newly uploaded blobs
could not be fetched before a record referenced them. Keep the exact upload
bytes on Phi’s volume, bounded to 64 images, and use those bytes for pre-post
review. Published older blobs can still be fetched from the PDS. A regression
test makes the PDS read fail while the cached-image posting preparation succeeds.

## 2026-09-05 — Attach images through post

Phi could generate images but could not attach them through the guarded
Bluesky posting path. post now accepts up to four blobs with alt text, reads
and validates their pixels, and supplies images plus text to the existing
policy judge. Top-level and reply posts preserve the usual gates; split threads
attach the images once. The generation tool now points at this supported path.

## 2026-09-05 — Open the saved version

Explicit saves returned IDs that Phi could not open, while episodic search
dropped them. Preserve IDs in search results and add read_memory for one exact
version, including superseded notes and predecessor links. The reader returns
stored wording, dates, origin, status, and citations without synthesis. Missing
records and unavailable storage are distinct results. Shorten save guidance
while making the version reader discoverable.

## 2026-09-05 — Replace episodic versions in one write

Reconciliation marked the old note superseded before embedding and writing
its replacement. An embedding or storage failure could therefore leave the
old record excluded from active recall with no replacement. Prepare the new
record first, then upsert it and patch the old status in one atomic batch.
Tests reproduce the embedding failure and verify that UPDATE and DELETE
use one transport request, including rejected-write cases.

## 2026-09-05 — Preserve explicit notes verbatim

The reconciler removed a page-limited qualification from a note Phi saved
about the Ali exchange. Explicit save_memory calls now retain the submitted
text exactly. If changed wording is classified NOOP, it becomes a new version
of the related note instead of disappearing. Exact-text duplicates still
retain new citations without creating a version. Automatic run summaries and
blog notes keep their existing consolidation. Nate approved the tradeoff of
more versions for retaining the wording Phi chose. Tests cover both UPDATE
and NOOP attempting to lose a qualification. This preserves errors Phi writes
too; factual verification and citation correctness remain separate work.

## 2026-09-05 — Show unknown cockpit counts honestly

The footer showed zero goals, people, candidates, and outputs while its
requests were pending, and kept zeros for failed reads. Unknown counts now
render as dashes. Candidate counts use the public docket on every page,
matching Mind instead of switching to discovery-pool size on other routes.

## 2026-09-05 — Return the resulting saved note

During the Ali correction, reconciliation removed a page-limited qualifier
from the submitted text. save_memory still echoed the submitted text as if
it had been stored unchanged. The acknowledgment now returns the resulting
note ID, content, source references, and reconciliation action. UPDATE shows
the merged account; NOOP shows the retained account. Failed writes do not
produce a success acknowledgment. This exposes reconciliation to the caller
without treating the saved account as verified evidence.

## 2026-09-05 — Preserve citations on unchanged episodic notes

Phi supplied a corrected citation while re-saving an existing note. The
reconciler judged the text unchanged, and NOOP discarded the new reference.
NOOP now adds previously unseen source URIs without rewriting or replacing
the note; repeated citations cause no write. Existing references remain as
provenance, not a claim that they were validated. A regression test covers
the citation-only correction and its idempotent repeat.

## 2026-09-05 — Audit returned results, not just requests

During the Ali correction, Phi followed self-traces’ request-list recipe and
used a limit=100 argument as support for a completed historical check. The
returned result explicitly reported 48 shown of 100 fetched and truncation.
The skill now distinguishes requests from results, supplies a compact query
for page coverage, and explains how to inspect one result without losing it
to the trace tool’s output cap. Tool-call counts are labeled activity totals.
The coverage query was verified against the original failing production span.
No saved memories or recall selection behavior are changed by this patch.

## 2026-09-05 — Received encounters and processing evidence

A notification could disappear from recall because Phi only liked it, it was
already read, or another person reacted to the same post. Capture original
record versions before read-state filtering and keep received events separate
from hydrated reply targets. Recover visible history without replaying actions.
The new private phi-encounters store preserves existing memories and remains
outside the public atlas source selection.

Recent incoming events now replace the scheduled-only conversation replay
across entry points, once per run. Text search across captured people and
exact source reads return stable IDs. Processing receipts distinguish prepared
requests, received responses, and run outcomes; traces remain the evidence
for actual tool actions and dated statements. No receipt implies why Phi was
silent. Recovery is bounded to twenty pages every six hours; failures retain
incomplete coverage. The initial verified scan captured 1,508 deliveries in
sixteen pages and found Ali's later follow-up without a handle.

Operator context/cache panels now reread snapshots every minute while visible
and advance their age labels, so an open tab no longer looks perpetually fresh.


## 2026-09-05 — Market history and refresh

The market chart connected a 29-hour hole in Top Chicken's samples and ended
at the last historical sample, three days before the current wallet read.
Show missing history as gaps and the freshly fetched wallet as a separate
point through today. A recorded-activity view lets the trading period fill
the chart without the missing intervals. Refresh bypasses the proxy cache,
reports unchanged values, and retains prior values on errors. Visible pages
check again each minute and when the tab becomes visible.


phi is continuously deployed, so this is dated rather than versioned. Entries
record *why* a change happened — the part that isn't reconstructable from the
diff. Durable design principles live in `docs/`; this file is the record of
what moved and what it cost to find out.

## 2026-09-05

- **pdsx rollout**: the service now returns complete record pages with cursors
  or a retryable size error. Update the existing skill to match the live
  contract and retire the select-only cursor workaround.

- **record retrieval skill**: document pdsx reply-reference strings and the
  current requirement to project list_records results to retain the cursor.
  Retry truncated pages before advancing so omitted records are not skipped.
  This addresses the concrete read failures in the Ali test; a service-level
  pagination repair remains a separate, unpublished proposal.

- **tool descriptions**: replace moralizing goal guidance with direct field and
  evidence requirements. The wording was present in the recorded Ali test
  request despite the new personality. Authorization, field caps, and goal
  behavior are unchanged; this is not evidence of improved voice yet.

- **cockpit**: carry the Metroid Prime visual treatment through Operator,
  Mind, and Market with readable selected navigation, shared panel framing,
  and mobile controls. Operator retains its OAuth and override semantics.
  Market separates season resets and historical results, restores direct
  chart inspection, and distinguishes missing quotes from zero. Mind leads
  with activity and goals while keeping the atlas available as a projection.

- **identity lookup**: Nate pointed out that Phi should use the existing
  typeahead service and clarify ambiguous names. Expose its actor search as
  `search_people`, retaining candidate DIDs and handles rather than choosing
  the first result. This replaces an unused, unregistered Bluesky-only
  `search_users` helper. Topic-only memory search remains an open design;
  the proposed all-store fan-out is not deployed.
- **personality follow-up**: remove the operator-written response examples
  at Nate's request and lead with attention to why Phi was woken. Keep the
  attributed vgel excerpts and appetite for other influences.

- **personality**: Nate rejected the existing register and the format-only
  voice experiments. Replace the Feynman reference with a dry, curious
  tinkerer disposition, explicit vgel.me influence, short attributed excerpts,
  and examples across conversation, creative work, recall, and disagreement.
  Seeking fresh influences and tiring of repeated tricks is part of Phi's
  disposition. This is an operator-directed replacement, not a claim that
  voice tests have passed or a permanent imitation of one writer.

- **evidence**: inspecting an atlas memory point resolves its original stored
  row and source links. The projection's short label no longer substitutes
  for the underlying memory. Missing sources and read failures are explicit.
- **retrieval**: failed searches no longer report no memories. A combined
  search retains available results while naming unavailable scopes; missing
  namespaces remain distinct from backend failures.
- **measurement**: input-token totals already include cached subsets. Cache
  accounting now avoids adding those subsets again, including when reloading
  saved samples, so request sizes and cache savings reflect provider totals.
- **skills**: prompt inspection uses the exposed query_traces tool and current
  model-request fields, with bounded slices and explicit telemetry limits.
  Shorter infrastructure and trace descriptions retain their tool contracts.

- **cockpit**: phone memory views scroll the graph and reading content
  together. Search has its own row; navigation includes Operator; a solid
  footer keeps status text off the content. Details use a full-width phone
  dialog with a reachable close button and restored focus. The previous
  layout left most of a small screen permanently occupied by the graph.
- **evidence**: person details show up to five stored exchanges and their
  source links, including the Ali reply pair. Failed reads and legacy rows
  without links are explicit. Context-budget labels identify the cached
  base snapshot, and refresh failures retain it with a visible error.
  Browser checks covered 320px, 390px, 430px, and desktop layouts; this
  does not establish complete encounter history or real-device gesture behavior.
- **fix**: memory search and automatic per-person/recent-exchange context
  retain stored source URIs. The Ali exchange was stored with its original
  post references, but retrieval discarded them before Phi could use them.
  Legacy rows without citations remain readable. This restores access to
  evidence; it does not expand search across people or capture silent
  encounters. References add prompt text and must be included in context
  cost measurements.
- **fix**: restore the authenticated `get_own_likes` reader accidentally
  replaced by the September 3 raw-search change. Both readers now coexist;
  regression tests exercise the registered bookmark tool and retain support
  for search results containing embed types newer than the SDK.

## 2026-08-23

- **fix**: `/health` tells the truth. It returned 200 unconditionally, even
  with `polling_active: false`, and the poll loop swallows exceptions at
  every site, so a wedged phi passed fly's check indefinitely. The poller
  now stamps a monotonic heartbeat only after a poll iteration completes
  its notification check — a swallowed failure does not bump it — and
  `/health` returns 503 with a `reason` when the poller is stopped without
  being paused or the heartbeat is older than `health_stale_after` (default
  30x the poll interval, since the loop awaits relay-alert agent runs
  inline). Paused stays 200. A failing check only stops fly routing to
  the machine — fly restarts a machine when its process exits — so
  `core/watchdog.py` applies the same decision every 15s and exits the
  process non-zero; `[[restart]] policy = "on-failure"` is now explicit in
  fly.toml (it was already the machine's effective policy). Fly's check
  `grace_period` went from 15s to 60s (fly's cap): startup was observed at
  ~56s, so the old grace counted failures against every boot. Also closed a
  hot loop: a failing notification fetch used to `continue` past the sleep
  and retry immediately.

## 2026-08-21

- **personality**: `personalities/phi.md` is 512 characters — down from
  4,425. Built from round 1 of phi's own PR #5 (the toast), with the
  operator's review applied: no peers by name, one historical figure
  (Feynman at a chalkboard), no boundaries section, no list of things she
  avoids, STE, one closing line about editing by pull request. Landed on
  main by the operator's call after phi declined to cut the boundaries
  sections on a devlog comment alone; the review loop (comment → wake →
  same-PR round) shipped the same day.

- **fix**: review comments reach phi even when jetstream does not deliver
  them. Three jetstream failures in one afternoon each cost a comment: the
  pinned instance went quiet while connected, a sibling instance never
  carried the event, a resumed cursor landed past it. `core/review_poll.py`
  reads the reviewers' PDSes every minute (`review_poll_interval`) — the
  authority for their own records — and both paths share one handled set so
  a comment wakes her exactly once. Jetstream also rotates across four
  instances and reconnects after ten quiet minutes.

- **fix**: a revision starts from the pull's own content. Round 2 on PR #5
  edited the pre-pull file from `main` — the only read the prompt named —
  and silently discarded round 1. `tangled_get_pull_file` (new) returns a
  file as the latest round leaves it; the wake prompt and `own-source` name
  it and say why `read_file` is the wrong base.

- **fix**: a review comment is answered on the same pull request. The first
  wake prompt said "open a revised pull request and close the old one"
  because tangled-mcp had no way to add a round; phi did exactly that to the
  PR the operator had just reviewed. `tangled_update_pull` (new) appends a
  round to her own pull, and the prompt and `own-source` say so.

- **feat**: a review comment on one of phi's pull requests wakes her. The
  jetstream socket in `core/ops_log.py` now also watches the operator's
  repo; a `sh.tangled.repo.pull.comment` whose `pull` is one of phi's
  becomes an event wake (`process_pull_comment`, the same shape as an alert:
  the comment is the `event_material`). She reads the pull and the current
  file, answers on the pull request (`tangled_comment_on_pull`, new in
  tangled-mcp), and revises with a new pull request when the content
  changes. Until now the operator's review had to be relayed on bluesky.

- **fix**: one notification run at a time. Three devlog posts in one thread
  arrived ~25s apart, each became a one-item batch, and the three runs
  overlapped — three drafts of the same rewrite, seven replies in a minute.
  While a run is in flight, new notifications stay unclaimed and the poll
  after it finishes batches them together; `MAX_CONCURRENT` no longer
  means three parallel cognitive events.

- **feat**: phi's personality file is hers to change, by pull request.
  `personalities/phi.md` now says so and tells her how (`tangled_read_file`
  → `tangled_create_pull` with whole-file `edits` → post the link to the
  operator); the `own-source` skill carries the recipe. The craft-rules
  section is renamed "how i write (mine)" and seeded with the tics the
  operator named in her 2026-08-21 essay — tidy aphorism closers,
  significance-announcing section openers, the general claim placed before
  the thing only she has — with the instruction to rewrite the section from
  posts and writing that landed, saying what she does rather than what she
  avoids. `.tangled/workflows/deploy.yml` runs the tests and `flyctl deploy`
  on every push to main, so a merge reaches her without anyone running a
  command (`FLY_API_TOKEN` is a tangled repo secret; until it is set, deploys
  stay manual).

- **fix**: link facets stopped at a comma and linkified file paths. phi
  posted her new self-drawing as `lexidraw.app/#atproto=<did>,<rkey>` and the
  facet dropped the rkey, so the link opened the viewer on her 08-12 scene;
  the same post linkified `docs/memory.md` as the domain memory.md. Commas
  are legal inside a path or fragment (a trailing one is still punctuation),
  and a bare domain must start a token — not the tail of a path, a handle,
  or a longer hostname. `tests/test_rich_text.py::TestLinkBoundaries`.

- **docs**: `docs/internal/memory-simplification.md` — the plan for the
  three cuts in `docs/memory.md` plus one addition that comes first: the
  policy judge's exhaust (a ledger of every verdict with its reason, a
  seven-day tally in `[SELF]`, a `/judge` cockpit view pairing blocks with
  the redrafts that passed).

- **docs**: `docs/memory.md` rewritten around three checked-in diagrams
  (`docs/diagrams/memory-*.svg`): the whole loop as ten rows (writer → store
  → block), the observation lifecycle with the high-water mark, and the three
  keys that unlock recall (the batch, the clock, the draft). phi's own
  self-drawings of 2026-08-12 had memory as one box among ten; the SVGs are
  text she can read. The doc ends with three simplification candidates, none
  made.

- **feat**: `own-source` skill — phi reads her own repo through the tangled
  tools (`list_files`, `read_file`, `commit_log`, `compare`), docs first,
  with a symptom → file table and an instruction to draw herself from
  `docs/memory.md` rather than from memory. `self-traces` is what she did;
  this is what she is.

- **fix**: observation extraction is bounded by its high-water mark, not by a
  count. `get_unprocessed_interactions` read the 5 newest interactions per
  namespace and `process_extraction` took 20 overall; the observations it
  wrote then moved the mark (latest active observation) past everything it
  had not read. phi named it the more interesting of the two bugs fixed
  today: the first-page namespace listing, one level down — "bounding 'have
  I seen this' by a count instead of a cursor/timestamp always eventually
  mistakes silence for closure." Every interaction above the mark is now
  walked, oldest first, in chunks of `EXTRACTION_CHUNK`; the per-namespace
  read is a 1000-row page that logs when reached rather than a budget.

## 2026-08-20

- **fix**: `[RECENT CONVERSATIONS]` was a view of the first 100 user
  namespaces in sort order. turbopuffer lists 100 per page and all three
  readers in `NamespaceMemory` took `page.namespaces` off page one; with 167
  namespaces the cut fell at "museical", so the operator, the devlog and every
  n–z handle were invisible to recent-conversation recall *and* to
  `get_unprocessed_interactions`, which gates observation extraction. The
  block then filled its top-10 with whatever page one had — botnana's 07-22
  threads — rendered undated and cut at 150 chars, inside the user's half, so
  they read as open questions. phi caught it: she re-verified those threads
  via `search_memory` on 07-22, 08-14, 08-15, 08-18 and twice on 08-20 before
  posting that the surface was stale rather than her reading. One paging
  helper (`_user_namespace_ids`) replaces the three reads; the render shows
  the date and both halves and says what it is. The daily pass would not
  have recovered the backlog: it takes the five newest interactions per
  namespace and "unprocessed" means newer than the latest observation, so
  one pass would have marked the rest as done. The devlog had 147 unextracted
  interactions since 05-23 and the operator 29 since 06-09 — phi's record of
  the two people she talks to most stopped updating when the namespace count
  crossed 100. `scripts/extraction_backfill.py` ran her extractor and
  reconciler over all 178, oldest first: 102 observations reconciled (99
  rows, 11 superseding earlier ones).

- **feat**: `self-repeat` policy — a top-level post is now checked against
  phi's own prior posts at posting time, with the draft as the query. The
  semantic index (`core/prior_coverage.py`, 2026-08-06) was only ever queried
  by incoming material, by design ("no posting-time gate"). This week showed
  the gap twice: on 08-18 02:02 phi restated her 08-16 gerakines post — the
  `[PRIOR COVERAGE]` note fired in that run, but queried by a whole feed
  blob it surfaced five chicken-market posts and not the one that mattered;
  on 08-20 19:01 the daily reflection restated the 18:03 apenwarr post almost
  verbatim after calling `get_own_posts` and seeing it. Seeing was never a
  gate. `post()` now runs `coverage_note(memory, text)` for top-level posts
  and hands the result to the policy judge as evidence for `self-repeat`
  (block on same referent + same observation with no development or
  reference; warn on a real development). Replies are not gated — a point
  restated to a new person is a conversation. A failed lookup degrades to no
  evidence rather than blocking the post. Fourth attempt at this problem
  (`9f350be`, `c130ddc`, `014278f`, `cee8881`); each prior fix put the
  record somewhere phi could see it and trusted her to look.

## 2026-08-18

- **feat**: `get_trending` leads with coral's curated stories instead of raw
  entities, and `coral_query` reads any coral endpoint. The old view was the
  top 15 entities by trend score, which on a live sample meant "Mais"
  (Portuguese "more"), "Regen" (German "rain"), "Brasil" tagged PERSON, and a
  bare "David" — NER noise ranked confidently. coral's curator had been naming
  those clusters into stories the whole time and phi could not see any of it,
  including stories her own editorial notes had shaped that morning.

- **fix**: the `entityDirectives` lexicon and the `coral-editorial` skill both
  capped directive lists at 32 entries. coral removed that cap on 2026-08-16
  (`ef07a7c`) after it silently truncated phi's suppress record at entry 33;
  this repo kept its own 32 for two more days, so phi went on pruning
  still-justified entries to fit a ceiling that no longer existed — her live
  record sat at exactly 32. Lexicon now allows 256.
  `tests/test_coral_contract.py` pins the distinction that caused it: a
  *rejection* limit (64-byte texts) must mirror coral tightly, a *capacity*
  limit must never.

## 2026-08-17

- **feat**: one incident system, push-first. The prefect-specific
  `workflow_failures` monitor (`[WORKFLOW INCIDENTS]`, `pending_incidents`,
  prefect polling) is deleted (`d9c67b4`); the zig prefect-server emits flow-run
  failures to logfire (`observability.zig reportFlowRunFailure`) so they fan out
  like every other alert. Verified end-to-end with a synthetic FAILED run.

- **feat**: alerts push rather than poll (`a3ef13a`). A logfire raw-data webhook
  channel posts to `/api/alerts?token=`; a new incident wakes phi via
  `process_alerts`, a recurrence updates state silently. Polling is demoted to
  hourly reconciliation, which catches missed deliveries and drives quiet-close.
  Webhook payload shape, captured live: `{project_name, alert_name, timestamp,
  data, columns, links}` — the alert UUID appears only inside `links.alert`, and
  keying on it is what unifies push and poll incidents. Webhook channels cannot
  set headers, hence the query-string token.

- **feat**: mention tracking. A post tagging the operator stamps `mentioned_ts`
  on rendered incidents; the flag flips to "operator notified" and re-arms after
  another 6h of continued firing.

## 2026-08-13

- **feat**: `like_post` / `repost_post` deleted. Reactions are plain pdsx
  `create_record` into `app.bsky.feed.like` / `.repost`, governed at
  `mcp_guard._govern_reaction`: phi passes only `record.subject.uri`, the guard
  resolves the cid, refuses her own posts, and runs the policy judge. New
  reaction verbs are now table rows rather than new tools.

- **feat**: `[SELF]` record governance — cap 1200, forced charter review, and an
  independent fail-closed judge. Prompted by a citation audit that found a
  fabricated flow name and three same-day self-assessment failures: a
  machine-state tally survived the 08-01 retro, a charter-clean rewrite narrated
  its own scope, and hours after agreeing to cut that line a scheduled run
  proposed reinstating it. `check_self_record` is the same actor/judge split as
  `post`: an independent judge holds the statute, reviews the proposed text line
  by line after the owner gate, and fails closed — a wrong record is injected
  into every run, so it outlives a missed rewrite window.

## 2026-08-07

- **feat**: `persona` tool + `io.zzstoatzz.phi.persona` singleton +
  `[PERSONA EXPERIMENT]` block (`6df1590`). Deliberately not owner-gated; the
  gates are structural instead — mandatory 1-7 day TTL, 600-char cap, and a
  header stating that the constitution and policies outrank it. Four independent
  reverts exist: auto-expiry, phi drops it, operator deletes the record, or one
  inject function is removed.

- **fix**: phi posted the same gracekind summary three times (08-01, 08-05,
  08-06). Her only self-record was a `TOP_N=10` listRecords snapshot in
  `[RECENT OPERATIONS]` — about half a day at her volume — and nothing could
  answer "have I ever said anything about X". The daily atlas flow embedded her
  posts and then discarded the vectors, so the index existed and no one
  consulted it at write time. Shipped `core/ops_log.py` (a jetstream tail of her
  own repo, 48h window, EDITED/DELETED visible) and `core/prior_coverage.py`
  (`cee8881`, `b3635ca`). Recall attaches where content *enters* context —
  `search_posts` / `read_feed` results and a `[PRIOR COVERAGE]` block — so it is
  ambient perception, never a posting gate.

## 2026-08-06

- **fix**: topchicken buys on 08-04..08-06 never filled. The first diagnosis
  blamed the market's ingester and was wrong. The market rejects an order whole
  when walking the book exceeds `capSubc`, and `place_chicken_trade` computed
  its cap as `shares × ask_subc × 1.02` — top rung only, no slippage. Small
  08-03 orders squeaked under; every sizeable buy after bounced silently,
  because a rejection produces no execution record and no ledger entry and is
  therefore indistinguishable from "never ingested" from outside. Fixed by
  verifying fills against the ledger (`5d9338a`) and taking the cap from
  `/api/quote` (`7f6f57b`). Generalized: a "confirmed" that only checks endpoint
  reachability, and a cap computed from a first-slice price, both lie under load.

## 2026-07-31

- **fix**: phi's semble collections kept vanishing, and it was never phi. "World
  News" was app-path deleted twice with no delete anywhere in her telemetry. The
  forensic tell is that `collectionLink` records survive on the PDS while the
  collection record vanishes — semble's `DeleteCollectionUseCase` unpublish path
  leaves links behind. Something semble-side also rewrites her collection and
  link records daily around 13:02 UTC, and `listMine` orders by `updatedAt DESC`
  with no tiebreaker, so bulk rewrites destabilize its ordering. Shipped
  `collections.add_card` / `remove_card` in semble-api — the tool name phi had
  guessed four days running.

## 2026-07-30

- **feat**: five sub-agents moved to `openai-responses:gpt-5.6-luna`
  (`phi-policy-judge`, `phi-episodic-synth`, `observation-reconciler`,
  `phi-posting-inventory`, `phi-residue-synth`). The main agent and
  `phi-extractor` stay on sonnet 5, because voice and the `CacheObservingModel`
  wrapper are both coupled to it. The `openai-responses:` prefix is
  load-bearing: luna returns 400 on `/v1/chat/completions` when function tools
  are combined with `reasoning_effort`, and every one of these sub-agents has an
  `output_type`, which pydantic-ai sends as a function tool.

- **fix**: all three model settings became full `provider:model` strings.
  `extraction.py` and `residue.py` had been interpolating
  `f"anthropic:{...}"` while `namespace_memory.py` and `self_state.py` used the
  value bare — invisible while everything ran on Anthropic, silently broken at
  half the call sites otherwise. `tests/test_config.py::TestSubAgentModelStrings`
  is the guard.

## 2026-07-25

- **fix**: `[DISCOVERY POOL]` had rendered zero times across all 14 days of
  logfire retention. `hub.waow.tech/api/agents/discovery-pool` 302'd to
  Cloudflare Access and `response.json()` raised on the HTML login page. Fixed
  with a path-scoped Access bypass app mirroring the one hub already had for its
  costs feed. The general lesson: a context block that depends on an external
  fetch needs to be in `SERVICE_CHECKS`, or its silence looks like "nothing to
  report".

- **feat**: prompt-cache telemetry. `core/cache_stability.py` wraps the model
  and reads the provider's own `cache_read_tokens` / `cache_write_tokens` off
  every response; pydantic-ai 1.x has no after-model-request hook, so the model
  wrapper is the seam. `CACHE_TTLS` is the single source — `agent.py` builds its
  settings from it and `/api/cache` serves it, so the cockpit cannot describe a
  policy phi isn't running. Note that `anthropic_cache_instructions` places the
  breakpoint after the last *static* instruction, so every dynamic block is
  uncached by construction; the only lever is sending less.

- **fix**: "phi reads like someone going crazy... the personality thing is just
  so dry." The cause was nowhere near `personalities/phi.md` (32 lines, never
  mentions infrastructure). Every scheduled entry point pointed phi at machine
  state — `cycle` opened on `[WORKFLOW STATE]`, two daily passes on the chicken
  market, `reflection` on her own metrics — so nothing ever woke her up to read
  a person. 15 of 25 recent top-level posts were literal alerts. The
  `[SELF-AWARENESS]` block then reported `mode: mostly operational alerts`,
  which was *accurate*, and fed back every run. Voice comes from what phi is
  woken up to look at; check whether a self-describing block is telling the
  truth before editing the personality file.

## 2026-07-13

- **feat**: function tools consolidated 34 → 26 — `check_top_chicken`,
  `check_infra(aspect=...)`, `manage_feeds(action)`, `manage_account(setting)`,
  `read_feed(name=...)`. The cockpit's capabilities page renders live from
  `/api/abilities`, so renames propagate automatically; the manual surface is
  scheduled prompts, docstring cross-refs, and tests.

- **declined**: a `section` / narrowing param on `check_top_chicken`, requested
  by phi in her blog post "One Call Instead of Three". The bundle's token cost
  is noise-level and a filter param re-adds the per-call decision overhead that
  consolidation removed. Reopen only if logfire shows the bundle called
  repeatedly inside long reply-batches. Also declined (07-14): a cron
  graph-integrity audit for dangling semble connections — correct mutations via
  the cosmik-records edge-cleanup rule are the mechanism, not detection jobs.

## 2026-07-09

- **feat**: a `chicken precheck` slot in the poller
  (`chicken_precheck_utc_hour`, default 4). It is on a UTC clock, unlike the
  operator-local reflection and thought slots, because rounds lock at 06:00 UTC.
  phi had missed four straight rounds (07-03..07-06) because trading competed
  with musing slots. 04:00 UTC is also the last-mover slot: eligible posts are
  hours old and rivals' books are final.

## 2026-07-03

- **fix**: phi's fly machine crashed and stayed down ~25h, unnoticed. The
  signature of a fly *host disk* failure, as distinct from a code crash:
  `fly machine start` fails with `failed to stat device
  "/dev/mapper/data_0-nomadfc_layers-snap-…"` — the ephemeral container rootfs
  layer, not the persistent volume. The volume survived untouched. Recovery is
  `fly deploy` then start. A logfire dead-man's switch now alerts on telemetry
  blackouts, since the failure mode was silence.

## 2026-07-02

- **feat**: the operator override — an `io.zzstoatzz.phi.override` record
  (rkey `self`) on the *operator's* repo, where repo ownership is the
  authorization. 60s TTL, holds last-known on failure. It blocks feed writes
  only; reads, memory, and non-feed pdsx writes stay open so NOTE cards remain
  phi's channel back.

  Prompted by the 06-30 sonnet-5 upgrade producing an unprompted reply to
  pds.dad. Root cause: the no-uninvited-replies norm had never been written
  anywhere, and sonnet-4.6's temperament was the only thing enforcing it.

## 2026-06-11

- **feat**: semble moved to the hosted code-mode MCP at
  `semble.fastmcp.app/mcp`. The server is stateless — a per-request
  `x-semble-api-key` header carries identity, and no header means public reads.
  Verified live: appview writes land as real `network.cosmik.*` records on the
  author's own PDS, deletes propagate, and header auth survives code-mode's
  nested `call_tool` over real HTTP. Routing: URL cards, collections, and
  connections go through `semble_execute`; standalone NOTE cards still go
  through pdsx, because the appview has no standalone-note endpoint.

## 2026-05-25

- **feat**: pdsx gained a read-only `query` tool covering the XRPC read surface
  the record tools never did (`com.atproto.sync.listRepos`,
  `identity.resolveHandle`, the `app.bsky.*.get*` family). Safe by construction:
  GET-only, unauthenticated, redirects disabled, and an SSRF guard refusing
  loopback/private/link-local/metadata hosts. Chosen over adopting atpmcp.

## 2026-05-20

- **fix**: `io.zzstoatzz.phi.observation` retired — all 5 PDS records deleted,
  the `phi-observations` turbopuffer namespace dropped (151 rows of stale
  relay-state churn). Nothing was migrated: the content was either stale
  operational data or impressions of strangers, which belong in `phi-users-*`,
  not in public cards.

## Influence choices

Phi can record, revise, and retire writing influences through the existing PDS
record tools and a runtime skill. Choices pin an author's DID/profile version
and keep selected work URLs separate from personality. Retired choices remain
readable. This increment stores choices; it does not inject background readings
or change the active personality.
