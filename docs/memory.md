# memory

where each thing phi remembers lives, who is allowed to write it, and which
key unlocks it when she reads. three diagrams carry the structure; the prose
here is what the diagrams cannot say. they are checked in as SVG so they can
be read as text from inside the repo (`docs/diagrams/`).

## one loop, ten rows

![every store, who writes it, which block reads it](diagrams/memory-map.svg)

every memory surface is a row with the same three cells: something writes
it, it lives in a store, a prompt block reads it. there are ten rows in three
stores:

| store | visibility | what lives there |
|---|---|---|
| turbopuffer namespaces | private to phi | `phi-users-{handle}` (interaction · observation · summary), `phi-episodic` (notes · run summaries), `phi-own-posts` (every post, id = rkey) |
| phi's PDS | public | `io.zzstoatzz.phi.{self,goal,persona}` (intent), `.atlas` / `.docket` (daily derived blobs), `network.cosmik.*` (her library, indexed by semble) |
| the fly volume | local | `ops_log.jsonl` — a 48h jetstream tail of her own repo; `own_posts_watermark.json` |

| row | written by | read as | trust |
|---|---|---|---|
| interaction | phi's reply inside a batch — `after_interaction`, verbatim user/bot pair | `[PAST EXCHANGES WITH @h]` | high |
| observation | daily extraction at 19:00 UTC → `phi-extractor` → `observation-reconciler` | `[OBSERVATIONS ABOUT @h]` — 10 nearest the batch text | medium |
| summary | prefect `phi-memory-synthesis` (`compact.py`), hourly, from observations + interactions | `[PHI'S SYNTHESIZED IMPRESSION OF @h]` | low — labeled *may hallucinate* |
| note | `save_memory`, `publish_blog` — deliberate | `[RELEVANT MEMORIES — synthesized]` — top-10 → `phi-episodic-synth` | medium |
| run summary | every scheduled run, unconditionally (`tags=[run-summary, <label>]`) | same block · `search_memory` ("have I done this") | medium |
| own post | jetstream tail of her repo; backfilled from PDS at start | `[PRIOR COVERAGE]` · the `self-repeat` judge | high |
| repo event | the same tail, 48h | `[RECENT OPERATIONS]` — edits and deletes visible | high |
| self · goal · persona | gated tools (`propose_goal_change` like-as-approval; self-record judge) | `[SELF]` `[GOALS]` `[PERSONA EXPERIMENT]` | highest |
| atlas · docket | prefect `phi-atlas`, daily — reads every turbopuffer namespace | `[ATLAS]` `[DOCKET]` | derived |
| card · collection · connection | semble tools, live-first; the `curate` flow only deletes | `[SEMBLE]` | higher — intentional, public |

two things the picture makes obvious: `phi-users-{handle}` is three rows with
three writers and three trust levels sharing one namespace, and the two
prefect flows (in `my-prefect-server`) are writers like any other — neither
is visible from inside this repo's code.

**not memory, but adjacent**: thread context is fetched live from the network
per batch and never stored; the policy judge reads `phi-own-posts` and recent
posts but writes nothing; logfire traces are what she *did* (`self-traces`
skill), memory is what she chose to write down.

`inspect_atlas(point_id=...)` follows an existing `tpuf_namespace` / `tpuf_id`
reference to the current stored memory row. It returns the complete stored
content, kind, timestamp, status (including superseded), and original source
URIs. The atlas label remains a dated projection; the backing row can have
changed since generation. Missing rows and failed reads are reported separately.
This lookup does not search across people or recreate missing encounters.

Stored `source_uris` survive tool search (scoped, unified, and tagged),
per-author observations and exchanges, and the recent-conversations view.
Each reference is rendered as `source: <uri>` so Phi can fetch the underlying
record. Legacy rows without references still render; no reference is inferred
from a summary's text. Carrying a reference does not verify the claim attached
to it. Search scope and automatic context selection are unchanged by this.

## how a reply becomes an observation

![interaction → high-water mark → extraction → reconciliation → recall](diagrams/memory-lifecycle.svg)

the observation is the only row derived from another row, and its lifecycle
is the part that has broken most often.

1. a reply in a batch is stored verbatim at once (`store_interaction`).
2. at 19:00 UTC, `process_extraction` reads every interaction above the
   namespace's **high-water mark** — the latest active observation — oldest
   first, `EXTRACTION_CHUNK` (8) at a time. the mark is the only bound; the
   per-namespace read is a 1000-row page that logs when it fills.
3. `phi-extractor` proposes facts from the chunk. it never sees existing
   observations, so it cannot pattern-match off a bad prior fact.
4. `observation-reconciler` compares each proposal with the 3 nearest active
   observations and returns ADD / UPDATE / NOOP / DELETE. UPDATE writes a new
   row with `supersedes` → the old id and patches the old row to
   `status=superseded`. nothing is deleted; the chain is provenance.
5. the next batch with that author renders the active set.

the mark is per namespace. the two 2026-08 bugs compounded because both
bounds were counts: a first-page namespace listing hid every handle sorting
after "museical" (100 of 167), and a five-row read cap moved the mark past
what it had not read. 178 interactions were recovered by
`scripts/extraction_backfill.py`; see the changelog for 08-20 and 08-21.

## three keys

![the batch, the clock, the draft](diagrams/memory-keys.svg)

at read time every block is unlocked by one of three keys. this is the
simplest true statement of how phi recalls:

- **the batch** — what people just said is the query. per-author blocks,
  `[RELEVANT MEMORIES]`, `[PRIOR COVERAGE]`, the shape of `[DISCOVERY POOL]`.
- **the clock** — state, no query. `[SELF]` `[GOALS]` `[RECENT OPERATIONS]`
  `[SEMBLE]` `[ATLAS]` `[DOCKET]`, and the path blocks (`[RECENT
  CONVERSATIONS]` on cycle and reflection).
- **the draft** — the text she is about to post is the query, inside the
  `post` tool, feeding the `self-repeat` policy.

scheduled runs have no batch, so batch-keyed blocks render empty there. that
is the oldest recurring failure (the 22:02 gracekind repeat, the botnana
staleness): a scheduled path perceives through tools, not a batch. the fixes
were to ride `[PRIOR COVERAGE]` on `search_posts` / `read_feed` results and
to add the draft key.

## why it is shaped this way

- **supersession, not deletion.** observations and episodic rows carry
  `status` and `supersedes`; only active rows reach the prompt; the chain
  stays as provenance.
- **episodic is synthesized, observations are not.** raw top-K from the
  vector store put stale "pending X" notes next to fresh ones with equal
  weight; `inject_episodic` now synthesizes top-K given goals + query.
  per-author observations are already curated by reconciliation on write.
- **writes to the library are live-first.** cards originate in the moment;
  the `curate` flow deletes, files, and trims and has no create tools. a
  review loop that authored from its own output once collapsed the library
  into one-topic self-synthesis.
- **residue was removed (2026-08-15).** a 7-item decaying buffer of
  "what runs left behind" carried claims with no ground truth, each carry
  reset its TTL, and the reflection copied them into goals; two resolved
  threads stayed flagged open for weeks. run summaries in episodic memory
  are the continuity mechanism now.

## where it could be simpler

none of these is made; each removes a row without removing a capability
anyone has asked for.

1. **retire the summary row and the hourly compact flow.** it is the only
   row labeled *may hallucinate*, rebuilt hourly from rows phi already sees,
   and the one surface carrying an external flow's voice into her per-author
   context. the likes-observation half of `compact` would move into the
   bot's extraction or be dropped.
2. **split run summaries out of episodic** (`phi-runs`, or a tag filter at
   synth time), so `[RELEVANT MEMORIES]` draws only on what she chose to
   remember and "have I done this" stays answerable from `search_memory`.
3. **name the keys in the code.** group the `inject_*` callbacks by key so
   figure 3 is visible in `agent.py` rather than reconstructed from twenty
   functions — the change that most helps phi draw herself accurately.

## the graph (`/memory`)

a visualization at `/memory` positions phi + user nodes by semantic
similarity of their observation vectors (PCA). only active observations
contribute.

see [system-prompt.md](system-prompt.md) for the block-by-block reference
and `skills/own-source` for how phi reads this document herself.

Explicit `search_memory` reports incomplete retrieval separately from an empty
successful search. Missing namespaces are identified; backend or embedding
failures are not evidence that no encounter occurred. Unified search retains
successful results and their citations when the other namespace fails. With
no current author, it queries episodic memory only rather than a blank-handle
user namespace. This does not provide cross-person search.

`search_people(query)` resolves a name or handle prefix through
typeahead.waow.tech, returning up to ten candidate handles and DIDs. Phi can
use an established handle with `search_memory(about=...)`; ambiguous matches
can be clarified in the conversation. Identity lookup does not establish a
prior encounter and cannot search conversation topics. The tool reports an
unavailable service separately from an empty candidate list. No structured
elicitation transport or automatic choice of person is added.


## Received encounters

`phi-encounters` stores original notification versions before filtering or
hydration. `(uri, cid, reason)` determines identity; replay preserves first
capture time. Read flags are not evidence of capture. Startup and six-hourly
recovery scans are bounded to twenty pages and do not dispatch actions. Scan
receipts distinguish incomplete traversal from cursor exhaustion; exhaustion
is not a claim about deleted or unavailable history.

Every run receives up to eight captured events indexed in the preceding
48 hours, replacing scheduled conversation replay. `search_encounters` searches
captured text across people; `read_encounter` opens the stored source version
and recent related processing receipts. Existing per-person and episodic
memories remain accessible through `search_memory`.

Run/request receipts record input preparation, provider response receipt, and
run outcomes. Event capture alone does not prove model exposure. Completion
does not establish a public action or a motive for silence. Confirmed tool
results and dated statements remain in the linked execution traces.

The public atlas still selects its existing per-person/episodic sources;
encounter and processing records are not added to that publication.

`save_memory` returns the resulting note ID, text, citations, and reconciliation
action after a successful write (or the retained note on NOOP). Explicit notes preserve the submitted wording; reconciliation chooses their
relationship to older versions without rewriting their text. Automatic run
summaries retain text consolidation.
The saved account and its citations remain claims, not independent verification.

An explicit save judged redundant (NOOP) still retains different submitted
wording as a separate note. It does not archive the existing account: a brief
confirmation must not displace a detailed correction just to preserve its text.


Scheduled-run summaries are stored in full as separate timestamped events
(`source=run:<label>`), not reconciled with similar older runs. General episodic
writes also exclude run-summary rows from consolidation. This keeps one run's
account from absorbing another run's actions; it does not independently verify
Phi's account. Explicit `save_memory` notes still preserve their wording.

`save_memory(..., supersedes_id="<active note id>")` corrects that exact version
without similarity selection or reconciliation. Read it first with `read_memory`.
Missing/superseded targets are refused; the original text remains readable and
source references are retained. Correction calls are serialized in Phi's process
and recheck the target before writing; this is not a distributed compare-and-swap
against external writers.
