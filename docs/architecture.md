# Architecture

Phi is one PydanticAI agent with several entry points. Each assembles `PhiDeps`,
a task and contextual evidence, then calls `agent.run()`. Actions happen through
tools within that run; the returned text is a logging summary. The reviewed
[architecture model](architecture-map.md) and source inventory are at `/architecture`.

The [memory and context map](memory.md) explains every surface's purpose and
origin. [System prompt](system-prompt.md) describes current injection; [safety](safety.md)
describes enforcement. Runtime workflows live in `skills/`; operator tooling lives
in `.claude/skills/`.

## Entry points

| Path | Trigger | Work |
|---|---|---|
| Notifications | Poll tick, 10 seconds by default | Read a batch of received events and decide what each exchange needs |
| Operator DM | Incoming messages in the private operator conversation | Interpret the specific request; respond privately when useful |
| Cycle | Configured operator-local thought slots | Follow Phi's attention; at most one public composition or none |
| People | A subset of thought slots | Read people and their work |
| Daily reflection | Configured operator-local reflection hour | Reflect on the day and update changed goal state |
| Bio | First unpaused tick when due, then every 24 hours | Review profile description; include avatar/header review weekly |
| Alert | Logfire webhook or watched relay incident; hourly alert reconciliation | Inspect the incident with fresh workload context |
| Pull comment/review | Forge events and review trigger | Read and review the identified patch or respond to review material |
| Chicken scout/precheck | External Prefect schedules/control triggers | Assess the current play-money market and act within trade restrictions |
| Publication curation / likes review | External weekly triggers | Read and curate material Phi wants to retain or recommend |
| Editorial | External daily trigger | Research developments, preserve sources and update Coral context |
| Character retrospective | External monthly trigger | Review the stored SELF account; keeping it unchanged is valid |
| Extraction | Daily reflection processing | Extract observations from unprocessed exchanges |

The bot's `notification_poller.py` owns local polling and due-time decisions;
`my-prefect-server/prefect.yaml` owns external schedules. Refer to those sources
for exact hours. Slot state seeds from history to avoid deploy-triggered repeats.
Logfire incidents replaced the separate Prefect failure monitor; there is no
second failure-polling schedule to configure.

Bio work runs in a tracked background task and never blocks startup. Its timeout
is three minutes, or ten when image review is due. Failed writes preserve the
existing profile; failed image-review passes remain due. Last completed review
state persists across restarts. Pause, voice reset and operator override apply.

## Notification and evidence flow

Notifications are captured before filtering or hydration. The handler groups
received events into a batch, fetches thread/author context and builds verified
reply references. Dynamic context adds relevant per-person and episodic history.
Phi calls tools; confirmed results and exchanges are recorded separately from
her summary of the run. Scheduled summaries retain work that produced no post.

New signals are facts to judge. Entry-point tasks identify the current activity;
block headers explain evidence and limits; tool descriptions and runtime skills
own procedure. A quiet run can be complete. The posting boundary independently
checks contact, prior coverage and public delivery, including all split parts.

## Models and cache

| Setting | Agents | Default |
|---|---|---|
| `agent_model` | Main Phi and observation extractor | `anthropic:claude-sonnet-5-5` |
| `policy_model` | Independent policy judge | `openai-responses:gpt-5.6-terra` |
| `extraction_model` | Episodic selector, reconciler, posting inventory and post-topic labels | `openai-responses:gpt-5.6-luna` |

Settings hold full provider/model identifiers. The `openai-responses:` prefix
selects the API needed for the configured reasoning/structured-output agents.
The main extractor uses prompted structured output for its configured Anthropic
model. Provider credentials and helper-model choices are independent.

`model_cache_settings` supplies Anthropic's 1-hour tool/instruction and 5-minute
message TTLs, or OpenAI's stable prompt-cache key. Context is memoized per run;
provider-reported accounting is observed, not inferred from configuration.
Switching models does not rewrite Phi's PDS personality or share caches.

MCP clients are fresh per run. Tool filtering and deferral live in `core/mcp_tools.py`;
[MCP integration](mcp.md) describes their families and failure handling. Skills
load procedural guidance on demand. Native tools and their risk declarations
are introspected for the cockpit and the policy judge. Read-only context previews,
offered-tool listings and budget assembly live in `core/context_diagnostics.py`;
they reuse the agent's registered blocks and MCP construction rather than
maintaining another prompt or tool catalogue.

## Identity and authority

Phi owns her live personality revisions, public writing and library. SELF and
goal scope changes retain their operator gates. A private operator request is
sufficient for `_is_owner`; existing public approval remains supported in an
unmixed batch. This establishes participation, not cryptographic action-bound
approval. The request still determines the authorized action and target.
Contact with someone else is a separate judgment. See [operator workflow](internal/operator-workflow.md).

Phi requests and reviews maintenance; Gardener is the maintenance identity;
Pi is its coding harness. Prefect orchestrates the workflow, currently using
exe.dev for the Gardener route, and Aperture supplies inference. Trusted workflow
code holds publishing credentials. The operator authorizes merging; a harness
response or completed run is not proof of publication, merge or deployment.

## External state producers

`my-prefect-server` builds relationship summaries/likes observations, the atlas
and the docket. Atlas projects memory and public records; docket proposes optional
work from that projection. They are available explicitly rather than injected
into every conversation. Phi alone authors and maintains her Semble library.

Coral discovers patterns of attention and consumes Phi's factual editorial
context. Phi's articles and public source library remain distinct from that
feedback channel. Influence records identify chosen reading; a background reader
is not connected to conversational runs.

The TypeSafe client in `services/typesafe.py` selects relevant market heuristics
against a current snapshot. `core/chicken_strategy.py` owns those questions and
PDS rule records. The shared client makes no automatic retries and closes at
shutdown. Selection failures are explicit; they do not append the old doctrine.
Trade restrictions are enforced by the trade tool, outside heuristic retrieval.
