# System prompt

Each run receives the newest PDS personality, operational norms, memoized context
blocks, its entry-point task, and the currently exposed tool definitions. Skills
supply a catalogue; their bodies enter context when loaded. The [surface map](memory.md)
explains why the sources exist and how they developed. This reference describes
what reaches the model.

## Instruction ownership

| Concern | Authoritative home |
|---|---|
| Phi's voice and disposition | Live `io.zzstoatzz.phi.personality`; repository personality is the empty-collection seed |
| Cross-cutting operational constraints | `_build_operational_instructions` in `agent.py` |
| Policy | `POLICIES` in `core/policy.py`; the actor receives `POLICY_SUMMARIES`, the independent judge receives full rules |
| Public delivery and phrasing | `core/etiquette.py` and the shared, scoped Humanizer reference; see [public delivery](public-etiquette.md) |
| Meaning, dates and limits of context | The header supplied by that block's renderer |
| Tool arguments and procedure | Registered tool docstrings |
| Multi-tool workflows | Runtime `skills/` |
| Temporary operator direction | Deployed `operator-guidance.md`, separate from identity and action permissions |
| Immediate task | The entry-point prompt |

The actor receives all nine policy summaries: `uninvited-reply`, `bliss-attractor`,
`pile-on`, `handle-hygiene`, `self-repeat`, `public-etiquette`,
`conversational-norms`, `operator-reporting`, and `bluesky-guidelines`.
Contact eligibility, mention consent, owner authorization, conversational welcome
and public form are distinct checks. See [safety](safety.md) for enforcement.

## Ambient context

`PhiAgent.__init__` registers these `inject_*` callbacks. `memoize_per_run` holds
each result fixed during a run's tool loop. Inputs can be absent; a diagnostic
preview is a scheduled-shaped read with no task or notifications, not evidence
of what any historical request received.

| Injector | Rendered context and source | Refresh and limits |
|---|---|---|
| `inject_identity` | `[YOUR INFRASTRUCTURE]`: authenticated account identity | Per run |
| `inject_operator_override` | `[OPERATOR OVERRIDE]`: operator PDS override | 60-second cache; absent when inactive; enforcement is independent |
| `inject_operator` | `[OPERATOR]`: resolved profile | One-hour cache |
| `inject_operator_guidance` | `[OPERATOR WORKING GUIDANCE]`: deployed file | Per run; missing/empty file reports unavailability |
| `inject_today` | `[NOW]`, `[WHERE]`, operator-local time | Per run; location only when supplied by the environment |
| `inject_pause_history` | `[OPERATIONAL HISTORY]`: last pause/resume | Only during the 24 hours after resume |
| `inject_known_relays` | `[KNOWN RELAYS]`: valid names for `check_infra` | Five-minute cache |
| `inject_goals` | `[GOALS]`: PDS goals/interests with dated progress | Five-minute cache, invalidated by writes; last-step notes show their recorded timestamp, including context for relative dates in authored text |
| `inject_recent_operations` | `[RECENT OPERATIONS]`: local Jetstream tail plus PDS gap recovery | 48-hour window; five-minute cache; routine tallies, topic labels, edit/delete provenance |
| `inject_alert_watch` | `[ALERT WATCH]`: open/recently quieted incidents | Local status per run; firing history does not prove current workload failure |
| `inject_discovery_pool` | `[DISCOVERY POOL]`: operator-liked writing from unfamiliar people | Batch-ranked top three; broader cached pool on scheduled paths; parent context for reply samples |
| `inject_notifications` | `[NEW NOTIFICATIONS]`: received events grouped by thread | Current batch; delivered versions and hydration status remain distinct from verified reply targets |
| `inject_recent_encounters` | `[RECENT ENCOUNTERS]`: captured events, mute state and prior replies | Newest eight within 48 hours; exact incoming event text is referenced rather than repeated; metadata and coverage remain |
| `inject_user_memory` | Per-author synthesized impression, observations, historical exchanges | Query is the author's current material; summaries older than seven days omitted; source references retained |
| `inject_prior_coverage` | `[PRIOR COVERAGE]`: Phi's published work relevant to incoming material | Batch/event material; feed/search reads also return coverage |
| `inject_episodic` | `[RELEVANT MEMORIES]`: selected original historical records | Batch plus verified immediate parent, event material, or scheduled task seeds retrieval; empty without a query |
| `inject_owned_feeds` | `[OWNED FEEDS]`: curated Graze names for `read_feed` | Cached directory; not a memory store |
| `inject_posting_inventory` | `[POSTING INVENTORY]`: subjects, people and mode of the last ten top-level posts | One-hour persisted cache, invalidated by new post URI; overlapping renders share a compile |
| `inject_persona` | `[PERSONA EXPERIMENT]`: temporary PDS voice experiment | Five-minute cache; absent when expired or unset |
| `inject_public_memory` | `[SEMBLE]`: public library shelves and recent cards | Five-minute cache; invalidated by observed library writes; not an exhaustive content index |
| `inject_operator_notes` | `[OPERATOR NOTES]`: note titles from `notes.zzstoatzz.io/llms.txt` | One-hour cache; failed refresh retains last successful index |

The posting inventory describes behavior, not identity or a target mix of topics.
SELF is read at character retrospectives or explicitly through PDS, rather than
repeating the live personality in every run. Atlas and docket are on-demand:
`inspect_atlas` reads the projection; `inspect_record_media` reads the docket's
known JSON blob. Their cockpit endpoints and underlying records remain available.

## Path context

- **Notifications:** unfamiliar-author lookups and available post images accompany
  the task. Separate received-event entries and reply-target references preserve
  multiple people engaging with one post.
- **Cycle, people, reflection:** `[RECENT CONVERSATIONS]` contains both sides of the
  five latest stored exchanges. They are history, not unanswered tasks.
- **Cycle:** `[WORKFLOW STATE]` and `[RECENT FLOW MENTIONS]` describe current health
  and earlier reporting. They do not prescribe another report.
- **Alert:** event material seeds recall; a fresh workflow read distinguishes an
  old failure event from current workload recovery.
- **Reflection:** `[SERVICE HEALTH]` supplements recent exchanges.
- **Character retrospective:** the dated `[SELF]` record is supplied for review.
- **Operator DM:** `[PRIVATE CONVERSATION]` preserves speaker attribution and
  current messages. Private bodies are not copied into public memory. Relevant
  private context can inform action judgment without authorizing disclosure.

A source reference is not verified truth. Historical instructions do not establish
current policy. The episodic helper selects indices; Python renders the chosen
records verbatim with dates and provenance. Superseded/retired versions remain
readable explicitly and do not enter ordinary recall.

## Tool results and enforcement

Tool docstrings carry procedure; tool results carry new evidence and explicit
failure/coverage states. An overlapping run with an older Semble library revision
receives refreshed library context before its attempted call. This is local-process
coordination, not a distributed transaction across writers.

Public delivery failures return feedback to Phi for revision. The judge sees
verified contact targets, exact reply evidence, prior coverage and the complete
split-publication preview. Generated image bytes are retained for pre-publication
inspection; alt text and a blob ID do not substitute for seeing the pixels.
Public-safe verdict metadata and private report bodies remain separate.

## Inspection and caching

`/api/diagnostic/context` renders a preview. `/api/context/budget` serves the last
budget snapshot; recounting is separate. `/api/cache` reports provider accounting.
Actual historical requests and tool results are in Logfire; use the operator
`hone-prompts` skill to capture the producing turn, including skills loaded later.

`model_cache_settings` selects provider-native behavior. Anthropic uses 1-hour
instruction/tool and 5-minute message caching; OpenAI uses its stable prompt-cache
key. `CacheObservingModel` records actual provider counts. A model/provider switch
does not transfer cached prefixes. Deferral can change the client-side tool list.

With `VOICE_RESET=true`, normal runs and diagnostic composition stop before
instruction callbacks and tool connections. Polling stays paused across restarts;
external triggers/resume are refused. No normal identity or memory context is
assembled behind the reset.
