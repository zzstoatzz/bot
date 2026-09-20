# plyr.fm stewardship inventory — 2026-09-19

## Decision and answered maintenance question

**Can Phi currently treat plyr.fm as fully supported for investigation and change
proposals, and use its green website check and cost total as a sufficient baseline?**
No. Investigation source supports its GitHub repository, but proposal source and
the live `pi-pr` schema exclude it. The current fleet check only GETs the frontend.
The cost dashboard provides a useful $70.37/month estimate with incomplete coverage,
not a reconciled invoice. These distinctions should reach Phi before more autonomy.

The selected small expansion is a dated plyr.fm evidence packet through the
existing fleet-health path, specified in [the implementation brief](plyr-stewardship-next-step.md).
It adds service understanding without new repositories, providers, schedulers, or
publication permissions. This inventory goal is complete; that implementation is
separate work. No production state was changed or workflow dispatched.

## Scope, sources, and freshness

Observed around 20:54–20:58 UTC on 2026-09-19. [Scoped evidence](evidence/plyr-stewardship-2026-09-19.json)
retains public probes, cost lines, sanitized machine facts, and selected live Prefect
schemas. Access failures below are observations, not evidence of service failure.

Source checkouts inspected:

- plyr.fm: `c93dfcbe0e464127d4bd7deb19c5fd2492f51eea`; GitHub main had advanced
  to `b06962b9d3cf8e8f2881454847bd4c53b78f16fe` when probed. Local source facts
  below are pinned observations, not a claim that all current main files match.
- my-prefect-server: `abbd167d7abd6caa35262c1a417875454a8957ba`.
- Bot: current worktree; earlier evaluation/feedback changes remain uncommitted.

Primary references: plyr.fm `STATUS.md`, `COSTS.md`,
`docs/internal/tools/agent-access.md`, `docs/internal/deployment/environments.md`,
`backend/fly.toml`, `backend/src/backend/api/{meta,stats}.py`, and
`.github/workflows/{deploy-prod,deploy-staging,deploy-moderation,deploy-redis,export-costs}.yml`.
Maintenance references: my-prefect-server `flows/{pi_agent,pi_pr,fleet_health}.py`,
`packages/mps/src/mps/workflow_requests.py`, `docs/operations.md`; bot
[`request_workflow`](../../src/bot/tools/workflows.py).
These sibling sources remain authoritative; this document does not replace them.

## Purpose and dependency map

plyr.fm is a communal audio application and ATProto reference implementation:
artists publish music, listeners play it, and identities and music records can
move between clients. PDS portability is a product objective, not proof that every
existing audio blob is successfully mirrored. The recent PDS-upload incident in
`STATUS.md` demonstrates that distinction.

| Component | Provider / resource | Role and evidence | Current confidence |
| --- | --- | --- | --- |
| Frontend | Cloudflare Pages `plyr-fm`; staging `plyr-fm-stg` | SvelteKit; documented production branch `production-fe`, staging `main` | Public page HTTP 200; account metadata inaccessible in this session |
| API | Fly `relay-api`, iad | FastAPI; app process, separate worker and Jetstream processes | Fly read access and public endpoints verified |
| Application database | Neon `plyr-prd`, `cold-butterfly-11920742` | Track/artist metadata, sessions and application data | Project discovery verified; `/stats` exercised an aggregate DB read |
| Other databases | Neon `plyr-stg`, `plyr-dev`, `plyr-moderation` | Separate environments and labeler data | All four projects found; no privileged SQL or load query run |
| Media | Cloudflare R2 audio/image buckets, including environment/private variants | Storage and public media delivery; user PDSes also hold records/blobs | Configured; current R2 byte counts and request costs unknown |
| Queue/cache | Fly `plyr-redis`, `plyr-redis-stg` | Docket tasks and cache | Cost feed lists both plus `plyr-redis-next`; the latter's consumer is unverified |
| ATProto ingestion | Dedicated Jetstream process | Consumes external stream and enqueues work | Machine started; cursor progress/lag unmeasured |
| Moderation | Fly `plyr-moderation`, separate Neon DB | Copyright/labeler service | Public health 200, labeler enabled |
| Transcoder | Fly `plyr-transcoder` | Rust audio conversion | Source config and historical suspended status only; absent from current cost lines is not proof of removal |
| Optional ML | Modal CLAP, Replicate genre inference | Enrichment/classification | Source documents dependencies; actual current spend/traffic unknown |
| Copyright matching | AudD | Metered audio identification | Dashboard derives $5 base, zero estimated overage; not an invoice |
| Observability | Logfire, Fly, Prefect fleet-health | Traces, process state and periodic probes | Health probes inspected; no current latency/error/queue trend established |

Authentication depends on ATProto OAuth and each user's PDS; those external
services can fail independently of plyr.fm's API. Media delivery, ingestion, uploads,
and moderation likewise have distinct failure modes.

## Current health and capacity evidence

- `https://plyr.fm/`: HTTP 200, 15,502 response bytes. This proves reachability,
  not playback or sign-in success.
- `https://api.plyr.fm/health`: HTTP 200, `status=ok`. The inspected handler
  returns a constant; it checks no database, Redis, queue, PDS, or media dependency.
- `https://api.plyr.fm/stats`: HTTP 200; 1,091 tracks, 111 artists, 15,700 plays,
  493,981 audio seconds. Source performs a Postgres aggregate read. These are
  cumulative counts, not concurrent users, throughput, or spare capacity.
- `https://moderation.plyr.fm/health`: HTTP 200, labeler enabled. No label write
  or signing/stream-delivery exercise was performed.
- Fly `relay-api`: three started machines (app 1 GiB, worker 2 GiB, Jetstream
  1 GiB), all shared 1 CPU in iad. Two additional machines are stopped; the
  stopped worker declares the running worker as its standby target. Stopped
  inventory alone is not an incident. All five report production source SHA
  `085c0cc089b0e7cfca0947741b599ba05bf59f3f`.
- Configured HTTP concurrency soft/hard limits are 200/250, not measured
  sustainable capacity. Worker and Jetstream restart policies are `always`;
  Jetstream is intended to be singleton. No queue age, worker heartbeat,
  ingestion lag, CPU/RSS trend, p95 latency, error-rate window, or load test was
  collected. Headroom remains **unknown**.
- Existing `fleet-health` checks only plyr.fm's frontend URL; the richer
  dependency observations above are not currently its plyr check.

## Cost baseline and its limits

[Hub feed](https://hub.waow.tech/api/costs.json), generated 08:00:20Z, has 15
plyr.fm lines totaling **$65.37**: Fly $49.17, Neon $15.20, Cloudflare $1.00.
The [plyr dashboard feed](https://api.plyr.fm/stats/costs), generated 20:05:17Z,
retains that `infra_as_of` and adds $5 AudD for **$70.37/month estimated**.
The hourly export workflow completed successfully at 20:05:21Z, run
[35466297165](https://github.com/zzstoatzz/plyr.fm/actions/runs/35466297165).
A fresh export is not a fresh upstream infrastructure measurement.

- Fly is current started inventory extrapolated at July list prices, not actual
  billed uptime. The feed explicitly excludes stopped rootfs measurement.
  Production API is $22.95, staging API $17.76; Redis variants, moderation,
  volumes and snapshots make up the rest. Do not infer savings without utilization.
- Neon is four equal $3.80 allocations of a $19 Launch base. Compute overage is
  explicitly uncomputed. June's always-on moderation concern is historical and
  must not be presented as a verified September endpoint configuration.
- Cloudflare has only the $1 domain line here. No attributed R2 storage/request
  lines were observed; that does not prove free or unused storage. The current
  upstream connector contains R2 allocation code, so June's documentation claim
  that attribution simply does not exist is stale.
- AudD reports 4,063 estimated requests against 6,000 free, with 1,937 remaining.
  Usage estimation comes from the exporter; billing-cycle and invoice agreement
  were not verified. Modal/Replicate and shared maintenance/inference overhead
  are not separately reconciled in this total.

Do not add the dashboard total to the hub total: the former already includes the
latter. No provider invoice was inspected. This is sufficient to identify coverage
and freshness gaps, not to claim a complete operating cost or a savings amount.

## Forge, execution, and authority boundaries

GitHub `zzstoatzz/plyr.fm` is the development/review and CI source. Its live default
branch is `main`; the local `origin` fetches GitHub and has both GitHub and Tangled
push URLs. Tangled `zzstoatzz.io/plyr.fm` is mirrored by release tooling. Live
Tangled main was `085c0cc…`, matching the deployed backend, while GitHub main was
`b06962b…`. These are intentionally different roles; never choose the mirror as
current development source merely because Gardener can publish Tangled pulls.

| Operation | Existing path | Scope / limitation |
| --- | --- | --- |
| Read source | Public GitHub clone; Gardener `pi_agent` repo map | plyr.fm supported; pin the investigated SHA |
| Request investigation | Phi owner-gated `request_workflow` and override; bearer to trusted bridge | Bridge requires Sprite pool, uses read-only Pi tools and idempotent request identity |
| Request proposal | Tool/bridge currently accepts plyr.fm | Downstream `pi_pr` source and live schema exclude it; **not end-to-end supported** |
| Publish Gardener pull | Trusted `pi_pr`, Gardener PDS handle/password Secret blocks | Tangled patch record; no GitHub PR publishing path demonstrated |
| Merge/release | Operator | Local GitHub auth reports admin/push capability; this does not delegate it to Phi or Gardener |
| Staging backend | GitHub main push | Auto-deploy, migrations via release command |
| Production backend | Published GitHub release, `FLY_API_TOKEN_PROD` | Latest observed release `2026.0919.060731`, published 06:07:32Z |
| Frontend production | `production-fe` branch promotion | Separate Cloudflare project; public reachability does not prove exact frontend SHA |
| Redis / moderation production | Path-filtered GitHub main pushes or manual dispatch | Exceptions to “main only deploys staging”; review affected workflow before merge |

The live `pi-pr` deployment `ec0cc6dc-bed2-4b93-80ba-41c15cb2a5cb` reports
`home-pool`, while the bridge source requires `phi-sprites-spike`. A separate
`sprites-spike` deployment supports the investigation schema. The bridge's live
workflow-to-deployment mapping was not inspected, so this does **not** prove all
current workflow dispatch is broken. It proves names and repo allowlists alone
are insufficient evidence of a valid route.

Credential custody: the operator's local GitHub/Fly auth is distinct from runtime
credentials; GitHub workflow secrets deploy services; Fly secrets hold database,
R2, OAuth encryption and queue credentials; Prefect Secret blocks supply trusted
maintenance publishers/providers; Sprite inference uses run-scoped Aperture grants.
Moderation HTTP auth, ATProto app password, and label signing key are distinct.
No values were exposed, rotated, copied into documents, or capability-tested by a
write. Exact token scopes and rotation readiness remain unverified.

## Worker/spindle access

Prefect connector required reauthentication. Existing local authenticated API
access succeeded: `home-pool` (process) and `phi-sprites-spike` (sprites) report
READY and unpaused. This is orchestration state, not a completed work probe.
Read-only deployment listing returned 48 entries. A name filter returned unrelated
rows, so final selection was performed locally before fetching specific IDs;
no unverified server-side filter was used as evidence of absence.

`tangled-infra/deploy/heavypad/spindle-ingress.yaml` describes public
`spindle.zzstoatzz.io` → k3s Traefik on the EU host → Tailscale → heavypad:6555.
The README's opening Funnel wording contradicts its later explanation and the
manifest; do not repeat it as current routing. Public root returned HTTP 200.
That establishes reachability, not CI execution or current host configuration.
SSH attempts as stoat and root both required an interactive Tailscale check and
were cancelled. No network settings changed. Current spindle process health,
worker disk, and job execution are unverified. plyr.fm's reviewed CI uses GitHub
Actions, so spindle access is not a prerequisite for this read-only expansion.

Neon discovery and GitHub/Fly reads worked. Cloudflare API access to the account
identified in plyr config failed authentication; Pages configuration and R2 usage
remain source-backed rather than live-verified.

## Jev compaction relevance

The [reviewed design](waow-stewardship.md#related-idea-jev-for-evidence-selection)
suggests selecting evidence separately from permissions. Here the full hub JSON
was 16,329 bytes; deterministic `project == "plyr.fm"` selection retained all 15
relevant lines in 3,725 bytes (about 77% less, measured with the same JSON encoder).
No model is needed to make that reduction. The service packet can be smaller by
summing cents in code while retaining source references and caveats.

No evidence collected here establishes that long tool histories or duplicate
investigations are a current bottleneck. Defer a retention experiment until actual
run measurements show one. If tested later, retain full evidence externally, pin
authority/constraints and unresolved incidents, retain uncertain items, and measure
lost necessary facts and reread cost—not just fewer tokens. This goal made no
jev calls and installed no compaction plugin.
