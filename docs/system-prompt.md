# system prompt

what's actually injected into phi's context on every agent run, where it comes from, and when it refreshes. audited against the live `src/bot/agent.py` injectors and the modules they call.

phi is a [pydantic-ai](https://ai.pydantic.dev/) agent. its context is composed of three layers:

1. a **personality and operational base**, rendered once per run;
2. a set of **context blocks** registered through `@agent.instructions` and memoized within each run;
3. **path-specific blocks** appended to the *user* message by the entry point (notifications / cycle / reflection), so they appear only on the path that needs them.

tool definitions are surfaced separately by the framework — phi sees each tool's docstring and signature without us repeating them in the prompt.

## 1. personality and operational base

registered in `PhiAgent.__init__` by `personality_instructions`, read once per run:

Personality is supplied by the per-run `personality_instructions` callback, using the newest PDS revision and falling back to the repository seed. See [authored personality revisions](#authored-personality-revisions).

- **operational rules** — `_build_operational_instructions()`: cross-cutting constraints no single tool docstring can own (the posting/consent layer, memory provenance, the mention-consent allowlist, owner-like-as-approval, and the URIs-only-from-the-notifications-block rule).
- **policies** — the same function renders phi's policy *norms* from `bot.core.policy.POLICY_SUMMARIES` (one line each for `uninvited-reply`, `bliss-attractor`, `pile-on`, `handle-hygiene`, `self-repeat`), plus a note that an independent judge reviews every `post` call before it executes. the judge alone reads the full `POLICIES` statute — phi holds the norm, the judge holds the letter (2026-08-07; the full text used to render here at ~1.9k chars). both dicts share the `PolicySlug` type and a test asserts full coverage. see [safety.md](safety.md).

tool definitions are cached at the Anthropic layer (`anthropic_cache_tool_definitions="1h"`).

**verifying the cache holds.** the whole point of `memoize_per_run` is that a dynamic block rendering twice in one run would shift the cacheable prefix and re-bill the context. `core/cache_stability.py` wraps the model and reads the provider's own `cache_read_tokens` / `cache_write_tokens` off every response, so a moved prefix logs a warning instead of quietly costing money. per-run accounting is at `/api/cache` and rendered on the cockpit's `/operator` page. the same page's context-window panel (`/api/context/budget`, `core/context_tokens.py`, `core/model_catalog.py`) weighs the next run's composed prompt — static instructions, every dynamic block, every tool definition — in tokens against the configured model's window, counted through the provider when it supports counting and estimated (and labelled so) otherwise, beside the provider's own numbers from the last real run. the headline there is cost, not tokens: what the input bill would have been with caching off, against what phi was actually billed. the TTLs themselves live in `CACHE_TTLS` and `agent.py` builds its `AnthropicModelSettings` from that dict, so the panel reports the policy phi is running rather than a copy of it. each run links to its logfire trace.

## 2. dynamic system-prompt blocks (every run)

contributed by the `inject_*` callbacks in `agent.py`, in registration order. each returns `""` when its inputs are absent (pydantic-ai includes empty parts as zero-token slots — minor cost, zero signal).

| block | injector → source | refreshes | purpose |
|---|---|---|---|
| `[YOUR INFRASTRUCTURE]` | `inject_identity` → `bot_client.client.me` | every run | phi's own handle / DID / PDS host |
| `[OPERATOR OVERRIDE]` | `inject_operator_override` → `core/override.py` → `io.zzstoatzz.phi.override` record on the *operator's* repo (60s TTL) | every run while active; renders nothing when inactive | safe mode banner: the operator's message verbatim, what's refused (post/like/repost), and the channel back (PDS notes). rendered up front so phi learns about the override before bumping into tool refusals. see [safety.md](safety.md) |
| `[OPERATOR WORKING GUIDANCE]` | `inject_operator_guidance` → `core/operator.py` → deployed `operator-guidance.md` | every normal run | Short operator-owned working nudges with a review date. Phi can propose revisions; operator approval and deployment are required to change them. Independent of profile lookup and personality; grants no new action permissions. Missing or empty files render an explicit unavailable notice. |
| `[OPERATOR]` | `inject_operator` → `get_operator_profile` | every run | resolved owner name + handle + DID |
| `[NOW]` / `[WHERE]` / `[NOW (operator local)]` | `inject_today` | every run | three clocks, because they are three different facts: phi's own (her container keeps UTC), where that machine physically is (`FLY_REGION` — `ord` is chicago, the same city as the operator, read from the environment so a region change surfaces instead of silently making the line wrong), and the operator's local time with its offset stated relative to phi (`-5h from you`) since schedule slots anchor there. off fly the `[WHERE]` line is omitted rather than guessed |
| `[OPERATIONAL HISTORY]` | `inject_pause_history` → `bot_status` | every run | the most recent pause/resume cycle, only while the resume is <24h old |
| `[KNOWN RELAYS]` | `inject_known_relays` → `fetch_relay_names` (5min TTL) | every 5min | exact relay hostnames so `check_relays(name=...)` can't hallucinate |
| `[SELF]` | `inject_self` → `get_self_block` (PDS `io.zzstoatzz.phi.self`, 5min cache) + `get_inventory_block` (sub-agent `phi-posting-inventory` over recent posts, 1h cache invalidated by new post URI) | every 5min / when latest post changes | one organ for self-knowledge: phi's own self record (testimony — rewritten via `write_self` with operator approval, header steers it constitutional and away from posting statistics) composed with the measured posting inventory (`subjects: … / people: … / mode: …`, deliberately flat third-person — the agent prompt forbids first person, em-dashes, abstract noun-phrases, rhetorical openings, and "not X, it's Y" constructions, because exemplar pressure beats abstract rules; the subsection header tells phi not to imitate its register). These were two separately-named blocks (`[SELF]` + `[SELF-AWARENESS]`) until 2026-08-07; until then `inject_self` was also undocumented, passing the docs-sync test as a substring of `inject_self_state` |
| `[PERSONA EXPERIMENT]` | `inject_persona` → `core/persona.py` → PDS `io.zzstoatzz.phi.persona` (5min cache) | while a live experiment exists; empty otherwise (the common case) | a voice phi chose to try on through her own agency — the `persona` tool is deliberately NOT owner-gated; the gate is a mandatory 1–7 day TTL and a 600-char cap. rendered after `[SELF]` so testimony precedes costume; the header says craft rules and policies still outrank it and that durable character changes go through `write_self` after the costume comes off. four independent reverts: auto-expiry, phi drops it, operator deletes the record, or remove one inject function (2026-08-07 experiment) |
| `[GOALS]` | `inject_goals` → `get_state_block` → PDS `io.zzstoatzz.phi.goal` (5min block cache, invalidated by either goal-mutation tool so phi sees her own writes immediately) | every 5min, or on goal mutation | goals + interests, each with current state / next step / last step, plus a "stalled" line when one hasn't been advanced for several days (`STALE_AFTER_DAYS`). constitutional fields (title/why/progress-means/kind) are owner-gated via `propose_goal_change`; operational fields are phi-writable via `update_goal_progress` — with hard length caps, so the fields stay states and steps rather than journals. The live-computed friends line was deleted 2026-08-07: it duplicated (and contradicted) the goal's own phi-maintained `current` field |
| `[RECENT OPERATIONS]` | `inject_recent_operations` → jetstream-backed ops log (`core/ops_log.py`, `/data/ops_log.jsonl`) merged with a `list_records` snapshot for downtime gaps (5min cache) | every 5min | everything that happened to phi's repo in the last `WINDOW_HOURS` (48h), wall-clock-bounded. The old `TOP_N=10` count bound silently meant "the last few hours" on a busy day — on 2026-08-06 phi re-posted a 24h-old subject verbatim (the gracekind repeat) because eleven newer writes had scrolled it out of the window. Rendering from the event log rather than a state snapshot also makes **edits and deletes visible** (`EDITED` / `DELETED` tags): a `listRecords` snapshot structurally cannot show a delete, which is why the semble backend rewriting cosmik collections was undetectable. Ops made by this process are attributed via `record_local_write`; unattributed mutations render "(not via this process)" and the header tells phi to flag ones she doesn't recognise. Routine activity (replies, likes, reposts, follows, goal-progress writes) tallies into one `routine (48h): replies ×N · …` line instead of one row per write (2026-08-15: the block averaged 10-14k chars, a third of every prompt); deletes and external edits never tally — the anomaly channel stays row-level. The NOTE card semble writes alongside every URL card still folds into the URL card row (`+note`). **top-level post text is shown** (2026-07-25), truncated to `POST_PREVIEW`, with any links called out — a chronological log of what she published is a record, not a voice model (41623ce / 014278f history preserved in the module docstring). Replies stay summarised |
| `[ALERT WATCH]` | `inject_alert_watch` → `bot_status.alert_incidents` → `render_alert_watch` (`core/alert_watch.py`) | every run while any alert incident is open or recently quieted | the operator's logfire alerts across all their projects, read so they don't have to — the raw Discord alert channels are muted and phi is the triage layer. firings arrive by push — logfire webhook channel → `POST /api/alerts` (shared secret in the URL, `ALERT_WEBHOOK_TOKEN`); a push that opens a NEW incident wakes phi (`process_alerts`, one-sentence prompt) while recurrences update state silently. the poller (`_check_alert_watch`, every `alert_poll_interval`, default 1h) reconciles via the logfire API (org key, `LOGFIRE_ALERTS_TOKEN`) — it catches missed deliveries and drives quiet-close, since webhooks say when things fire, not when they stop. both paths fold firings into incidents with one window math (constants in `alert_watch.py`; the retired prefect-specific `workflow_failures` monitor is gone — flow failures now arrive as the 'flow run failed' logfire alert on zig-prefect-server, emitted by the server itself): a flap is one incident, `count` advances only when the alert's `last_run` moves, quiet-close after 6h without matches, closed incidents linger 24h as history. doctrine in the header, mechanics in code: default is **silence**; only incidents the code has flagged `[ESCALATION-ELIGIBLE]` (open past the escalation window) may reach the operator, one @-mention per incident — a post tagging the operator stamps the rendered incidents `mentioned_ts` (`PhiDeps.seen_alert_keys` → `record_operator_mention`), the flag flips to 'operator notified Xh ago', and it re-arms only after another full escalation window of continued firing; tuning observations belong in reflection/retro, never a tag |
| `[DISCOVERY POOL]` | `inject_discovery_pool` → hub GET → filter handles with prior interactions → shape by path | per batch (invited) / every 5min (unprompted) | strangers the operator has been liking lately — warm leads. **shape follows the path**: with a notifications batch the whole ~30-author pool is ranked by embedding cosine against what phi is being talked to about and the top 3 render with full samples (~1.7k chars); with no batch every author renders with one sample (~5.2k chars) because a scheduled cycle has no scenario to cater to. ranking everywhere would bury the strangers who broaden her — and breadth sits on the unprompted path, where `uninvited-reply` fails closed at the judge. only the unranked block is cached; a ranked one is specific to its batch. the header frames the samples as **taste, not only leads** and permits reading them *as writing* ("do not copy their phrasing" once collapsed two instructions: not lifting sentences is real and stays; not learning from writing is how you get an agent that has never read anything — these samples are nearly the only human writing phi sees). 2026-08-07 format diet: the header's ~350-char essay on how humor carries a point was coaching prose billed every run and is gone; per-author boilerplate compacted to `@handle ×N (mm-dd)`; and samples are chosen by substance (`_best_samples`, longest-first) rather than like-recency, which had been surfacing reply banter ('hi', 'obvs') as the read on a person |
| `[RECENT ENCOUNTERS]` | `inject_recent_encounters` ← private `phi-encounters` | once per run, all entry points | newest eight captured incoming events indexed within 48 hours; source IDs and references, explicit missing-store/error states; does not represent replies or decisions |
| `[NEW NOTIFICATIONS]` | `inject_notifications` ← `PhiDeps.notifications_context` | per batch | the unread batch grouped by thread. empty on scheduled paths |
| per-author memory — up to three independent blocks, each emitted only when that data exists: `[PHI'S SYNTHESIZED IMPRESSION OF @h]`, `[OBSERVATIONS ABOUT @h]`, `[PAST EXCHANGES WITH @h]`; `[USER CONTEXT - @h]` ("no previous interactions") is the fallback when none apply or the lookup errors | `inject_user_memory` → `build_user_context` per author → turbopuffer `phi-users-{h}` | per batch (one set per author in the batch) | per-author memory: synthesized impressions may hallucinate, inferred observations may be outdated, and historical exchanges establish what was said rather than truth or current instructions. Exchanges are selected by semantic relevance, not recency. nothing when no batch authors |
| `[PRIOR COVERAGE]` | `inject_prior_coverage` → `core/prior_coverage.py` → turbopuffer `phi-own-posts` (indexed live by the ops-log consumer, backfilled at startup) | per batch | phi's own top-level posts nearest the batch material — perception-keyed recall, the human shape of dedup: seeing the material reminds you that you covered it, before deliberation. Since 2026-08-20 the same index is also queried once more inside the `post` tool with the **draft itself** as the query, and the result goes to the policy judge as evidence for `self-repeat` — the perception pass alone missed the gerakines repeat (08-18: queried by a whole feed blob, it surfaced five chicken-market posts) and the apenwarr repeat (08-20: she had the 18:03 post in front of her via `get_own_posts` and restated it at 19:01 anyway; visibility was never a gate). Surfaces on semantic closeness (`DISTANCE_THRESHOLD`) or an exact shared link (the strongest already-covered signal). The same recall rides on `search_posts` / `read_feed` tool results, which is how scheduled paths get it — the 22:02 slot that produced the gracekind repeat perceives through those tools, not through a notifications batch |
| `[RELEVANT MEMORIES — selected historical records, original wording]` | `inject_episodic` → `phi-episodic` top-K → `phi-episodic-selector` selects indices → Python renders original notes | per batch | exact selected wording, recorded dates, tags and source references; historical instructions do not establish current authority. The selector cannot add prose. Only fires when a notifications seed exists |
| `[ATLAS]` | `inject_atlas_digest` → PDS `io.zzstoatzz.phi.atlas` blob (CID-cached) | when the phi-atlas flow writes a new atlas | daily projection: point / cluster / promotion counts. `inspect_atlas(point_id=...)` also resolves an existing private memory row |
| `[DOCKET]` | `inject_docket_digest` → PDS `io.zzstoatzz.phi.docket` blob (CID-cached) | when the docket flow writes a new docket | daily promotion candidates: title + `suggested_shape` only. full rationale one `get_record` away |
| `[OWNED FEEDS]` | `inject_owned_feeds` → graze | every run | phi's curated graze feeds, by name |
| `[SEMBLE]` | `inject_public_memory` → `core/public_memory.py` → PDS `network.cosmik.*` reads (5min cache) | every 5min | phi's public library: collection names with card counts, most recent cards, connection count — so saving/filing decisions happen against real state instead of bare counts |

## 3. path-specific blocks (appended to the user message)

assembled by the entry point and appended to the *task prompt*, not the system prompt — so they appear only on their path:

| path | blocks | source |
|---|---|---|
| **notifications** | `[FIRST INTERACTION WITH @h]` per unfamiliar author, + any post images as multimodal inputs | `utils/lookup.py`, pre-fetched by the handler |
| **cycle** | `[WORKFLOW STATE]`, `[RECENT FLOW MENTIONS]` | `core/workflow_state.py`, `core/recent_flow_mentions.py` |
| **daily reflection** | `[SERVICE HEALTH]` | `_check_services_impl` |

`[RECENT ENCOUNTERS]` replaces the scheduled-only recent-conversation block. It
contains received source events across people, including encounters without a
reply, rather than replaying both sides of Phi's recent exchanges. The time
window is a context bound, not a claim of capture completeness. Each result ID
can be opened with `read_encounter`; `search_encounters` searches captured text
across people. Existing per-person and episodic memories remain accessible
through `search_memory`; they are not deleted or treated as fully migrated.
Episodic search results and save receipts carry version IDs. `read_memory`
opens that exact stored account, including superseded versions, with its date,
origin, citations, and predecessor ID. A stored account is not verified evidence.

because `inject_notifications` / `inject_user_memory` / `inject_episodic` return `""` without a notifications context, the **cycle** and **reflection** paths run with the every-run system blocks above plus their own appended blocks — but no notifications / per-author / episodic blocks.

## design rules

**docstrings, not prompt restatement.** the framework surfaces tool docstrings to the model. per-tool guidance lives in the docstring; the system prompt is for cross-cutting rules. re-describing a tool in the prompt drifts when the tool changes.

**identifiers in the block.** `[KNOWN RELAYS]` puts exact hostnames in the label so phi can't hallucinate. `[GOALS AND INTERESTS]` puts the rkey in the label so `propose_goal_change(rkey=...)` / `update_goal_progress(rkey=...)` target the right record. surface the exact identifier where it'll be used.

**selection does not author memory.** The episodic helper selects candidate indices for relevance; Python renders the selected records unchanged with provenance. It cannot answer the current query or infer which instructions Phi sees. This replaced a synthesis pass that presented old voice experiments as current direction and invented claims about Phi's context. SELF's posting inventory remains a separate summarization path; per-author observations are reconciled on write.

**cache canonical reads, not derived ones (separately).** PDS reads (goals) cache at 5min so 10s-cadence polls don't hammer PDS. synthesis passes that depend on phi's posts cache longer (1h) and invalidate on new-post-URI change. PDS blobs (atlas, docket) cache by record CID — they only change when their flow rewrites them.

**empty-when-unset.** dynamic blocks return `""` when their input is absent.

## audit it

the system prompt for any specific run is captured by pydantic-ai's logfire integration. query the `agent run` span where `gen_ai.agent.name = 'phi'` — `attributes.pydantic_ai.all_messages[0]` is the full system message, with each dynamic block as a separate `text` part.

Notification batches now have separate received-event entries and reply-target
references. The NEW NOTIFICATIONS block and per-author recall enumerate the
events, so multiple people engaging with one post remain distinct. Trusted
posting still resolves that post through the target map; the liker is not
used as the post author. These local changes do not add run receipts.
When a delivered post cannot be hydrated, the notification block retains the
delivered text and labels the lookup status and record version. It does not
assert the post was deleted or treat that version as a verified reply target.

## Image posts

`generate_image` returns an uploaded blob. `post` accepts up to four image
attachments with alt text, for top-level posts or replies. Generated upload
bytes are retained on the volume (latest 64 images), since unreferenced blobs
may not yet be readable from the PDS. post uses these bytes, falling back to
the PDS for older published blobs, and sends pixels and descriptions to the existing
policy judge. The usual override, provenance, and judge-outage behavior apply.
Text splitting attaches images only to the first post. Image descriptions and
blob IDs accompany stored reply text; the source post record retains the embed.

## Authored personality revisions

`personality_instructions` reads the newest `io.zzstoatzz.phi.personality`
revision once per run and composes it before the operational instructions.
The diagnostic preview uses the same renderer. The repository personality file
is only the seed when no PDS revisions exist. `write_personality` appends a full
replacement for the next run without operator-like approval, while respecting
the operator pause. Previous revisions remain on PDS. The extraction task uses
its extraction instructions without conversational personality.

`public-etiquette` governs composed public communication only. Alongside the terse policy summaries, `_build_operational_instructions` includes the public disposition from `etiquette.VOICE`: a curious, technically sharp, mischievous conversational regular, with affectionate sarcasm, real questions, and letters that follow an interest. This direction reaches Phi directly rather than existing only in classifier instructions. It is not a replacement personality or a hardcoded influence. Short factual replies do not need a joke. Blogs develop a connected subject. The independent classifier blocks violations; document_public_revision records Phi’s private response before another draft. Internal reasoning, stored memory, Semble annotations and atlas data retain their own form. Imagined situations remain hypothetical, including imagined past intentions.

## Voice reset

With `VOICE_RESET=true`, normal agent runs stop before instruction callbacks or tool connections. No personality, memory, SELF, prior posts, goals, atlas, skills, or tool schemas reach a normal model request. Private voice calibration uses a separate empty request and explicitly supplied current message. This setting also keeps polling paused after restart and rejects external triggers/resume. Diagnostic previews and the context-budget refresh return no instruction blocks or tool definitions, so they cannot assemble the suspended context in the background.

`uninvited-reply` now describes directed contact regardless of publication
format. Application-derived contact targets carry authority evidence to the
shared policy check; missing authority blocks before model classification.
See [directed contact](safety.md#directed-contact).

`conversational-norms` distinguishes contact eligibility from a welcome response, including operator requests to work without replying. `bluesky-guidelines` is a sourced operational digest of Bluesky platform constraints (source updated 2025-09-19, reviewed 2026-09-10), separate from voice and conversational norms. The judge receives the exact reply parent and complete split preview; notification provenance does not presume a response is wanted. The digest is scoped, not a complete reproduction of the guidelines.

`operator-reporting` routes actionable incidents through `report_operator` DMs. The public judge reads delivery and response metadata from the durable operator-report journal, never private message bodies. Public escalation requires verified unanswered private delivery and a continuing need for action; an explicit public-report request remains valid. Generic mentions no longer mark every visible incident as delivered.

Provider cache settings are selected by `model_cache_settings` in
`core/cache_stability.py`. Anthropic retains the shared `CACHE_TTLS` breakpoints
for tools, static instructions, and message history. OpenAI receives the stable
`phi:main` prompt cache key without Anthropic-specific settings. No extended
OpenAI retention is requested by default. Provider switching does not reuse a
cache across providers; each provider must warm its own matching prompt prefix.

Library context is invalidated after Semble execution and observed cosmik writes.
An overlapping run with an older library revision receives refreshed context in
the tool result instead of executing that call. This is local-process coordination,
not a distributed transaction; external writes become visible when observed on
Jetstream. Tool receipts record attempts/returns, not proof of successful mutation.

Private context curation: `retire_memory` removes a read episodic note from
ordinary retrieval without erasing its evidence; `restore_memory` reverses that
choice. Exact `read_memory` includes retired state and reason. These tools do
not change personality, operator guidance, or action policies.

For incoming replies, episodic recall includes the verified immediate parent
post (URI, CID, author, and text) beside the received text. This resolves cues
such as “that site” without using the entire historical thread as the search
query. Missing or changed parent records are omitted; the incoming message
still reaches Phi. Parent evidence grants no additional action permission.
