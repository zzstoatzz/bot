# Evergreen health-check survey — 2026-09-20

This is a read-only survey of health-check coverage and meaning, not proof that
every product workflow works. No services, checks, schedules, or deployments were
changed. Three GPT-5.6 Luna agents inspected project sources; the primary agent
verified the public inventory, live monitor, selected response bodies, and the
active Prefect deployment and recent run.

## Verified fleet-level findings

- The published `https://nate.tngl.io/services.json` exactly matched Evergreen's
  local inventory at `fec9f92f0ef3c69334415017804bf1d44097030d`.
- It lists **48 projects/resource groups**, **30 with checks**, **47 endpoints**,
  and **18 groups without checks**. A missing endpoint is not an outage verdict.
- Evergreen's live `/status` sweep at **2026-09-20 19:31:43 UTC** returned HTTP
  200 for all 47 endpoints. This is one availability observation, not an outcome audit.
- `worker/src/index.ts:34` checks HTTP success, follows redirects, and cancels the
  response body. It does not evaluate JSON health fields, artifact ages, or MCP
  JSON-RPC results. `site/checker.js:3` does validate report freshness and inventory
  completeness; that verifies the monitor report, not the age of underlying work.
- **The scheduled fleet sweep is not the Evergreen inventory sweep.** Live Prefect
  deployment `fb012d28-b91e-48f9-af2a-e55fc2ce1b4d` is active at minutes
  3/18/33/48 and pins `@abbd167d7abd6caa35262c1a417875454a8957ba`. Its source checks
  seven URLs plus Stream's deep check. Completed run
  `82b2af38-b97a-4e4e-aeb3-cd4819a86481`, 19:33:13–19:33:36 UTC, confirms exactly
  those eight results: Stream deep, Stream site, relay-eval, Jetstream, hub,
  Coral, plyr.fm, and Prefect. All passed.
- `mcp-fleet-health` deployment `b356a5ff-8022-4b16-82e1-57e646623190` is active
  hourly at minute 12, using the same package pin. It is a separate MCP sweep.
- Evergreen's `docs/inventory.md` describes quarter-hour checks of its shared
  inventory. A dated Gardener incident report describes a broader shipped sweep.
  Neither describes the currently verified fleet deployment's coverage. This
  mismatch should be reconciled before relying on scheduled whole-fleet coverage.

The Prefect connector required reauthentication. Deployment and run facts above
were instead read through the existing authenticated Prefect client settings on
Phi's Fly machine, with only selected non-secret fields returned.

## How to read the project survey

An HTTP 200 can be meaningful when the endpoint itself refuses success on stalled
work. Returning more JSON fields without changing the verdict does not improve
Evergreen's check. A static site's successful response can be an appropriate basic
availability check; it need not imitate a background worker's heartbeat.

Source reviews describe the inspected checkout or pinned commit. Except for Phi,
whose deployed Python was verified in the preceding release, we did not prove
that every deployment is byte-identical to its local source. Live bodies confirm
only the sampled response. Suggested improvements are proposals, not changes.

## Reconciliation shipped later on 2026-09-20

Evergreen `2e249e3` is merged and deployed as Worker version
`4c89e9a7-d807-4231-93b3-0a09b79ad32f`. The published inventory and Worker agree
on 48 endpoints: Typeahead now uses `/health/freshness`, and zlay has separate
database readiness and ingest-progress checks. All 48 passed live validation.

my-prefect-server `3d7d099ef0e17cd335d6f8161a1189c0b0a80508` is merged in both
remotes and pinned on the existing active quarter-hour fleet deployment. It reads
Evergreen's published inventory/report and rejects stale, partial, duplicated,
renamed or contradictory results. Unhealthy endpoints remain findings, while
an incomplete sweep fails. Stream's deep check and three supplemental probes
(Jetstream, hub costs, relay-eval latest) remain.

Production run `6a7be88d-024b-4fb3-8708-d35278753c32` completed at
**20:05:52 UTC** with **52 passing results**, including all 48 inventory endpoints
and both newly selected checks. CI passed 438 tests, lint, formatting, typing,
deployment validation, and frontend checks. Evergreen's seven contract tests and
Worker dry-run passed. Other backend freshness gaps below remain proposals.

## Recommended order

1. Reconcile the scheduled fleet sweep with the actual Evergreen inventory; verify
   the deployment pin and resulting per-target output, not just registration.
2. Use Typeahead's existing `/health/freshness` (currently `/stats`) and add zlay's
   existing `/_healthz` alongside DB readiness. Both already communicate failure
   through HTTP status; no new shared reporting protocol is needed.
3. Strengthen endpoints for the substantive data paths: plyr API/transcoder,
   pub-search, pollz, and find-bufo's bot. Base each on its actual work and expected
   quiet periods. Do not restart healthy processes for every external dependency outage.
4. Use existing output/progress evidence for background projects before adding
   new endpoints: Punch cursor age, race38 stream progress, MCP atlas publication
   age, and scheduled workflow outputs. Configuration and a successful flow state
   alone do not establish delivery of the intended result.
5. Leave simple static-site availability checks simple. First establish ownership
   and intended operation for unassigned storage and intentionally suspended apps.

## Additional live checks

- Typeahead `/health/freshness` returned 200 with `ok=true`, `stale=false`, a
  successful search probe, replica lag 176 seconds, and snapshot age 124560
  seconds. Its code returns 503 when its freshness criteria fail.
- zlay `/_healthz` returned 200; source distinguishes it from the inventory's
  DB-readiness `/_health` path.
- Moderation `/health` returned `labeler_enabled=true`, but its handler always
  returns HTTP 200. Merely changing the inventory URL would not make that flag
  actionable to Evergreen.
- Relay-eval `/api/status` returned a 24-run coverage window with per-relay
  `behind_lately` findings. Those findings are JSON data, not an HTTP failure
  verdict. Do not treat intentionally scoped third-party relays as outages
  without interpreting their scope.
- Status `/_health` returned 200 with `status=ok`. Its deployment config uses
  that route, but the dependency semantics were not established in this survey.

## Project findings

“Basic” means the configured check establishes reachability, not the project's
end-to-end outcome. “Partial” means a specific useful property is checked, with
remaining gaps. “None” refers only to Evergreen, not all monitoring everywhere.
Paths in the source column are relative to each project's local checkout.

| Project | Current Evergreen check | Assessment and smallest useful next step | Source evidence |
| --- | --- | --- | --- |
| plyr.fm | API/transcoder health, moderation root, frontend/docs, MCP initialize | **Basic.** API/transcoder return constant ok; moderation health only reports configuration. Check actual serving dependencies and pending-work progress; MCP response must be validated, not just HTTP status. | `backend/src/backend/api/meta.py:26`; `services/transcoder/src/main.rs:106`; `services/moderation/src/handlers.rs:81` |
| typeahead | `/stats`, ingester `/health` | **Partial; better check exists.** Switch Worker check to `/health/freshness`, which evaluates serving readiness, replica/snapshot freshness and a real search canary. Ingester's live body exposes queues and write/source timestamps; status semantics were not fully traced. | `src/handlers/freshness.ts:47`; `src/handlers/freshness.ts:120` |
| pub-search | Backend `/health`, frontend, MCP initialize | **Basic.** Backend health is constant ok. Add a bounded serving-index/query check and freshness expectation; HTTP-successful MCP errors are currently invisible. | `backend/src/server.zig:133` |
| stream | Human `/status` | **Partial overall, basic in Evergreen.** Separate scheduled deep check samples upstream progress and compaction. Evergreen discards those counters. Reuse the deep checks or expose their meaningful verdict, preserving startup state. | `src/internal/serve/endpoints.zig:21`; pinned `my-prefect-server/flows/fleet_health.py:127` |
| rally | Website | **Basic.** D1/indexing could stop while page serves. Check a bounded data read and indexer progress where work is expected. | `worker/index.ts` application and ingestion routes |
| doodl | Website | **Basic, reasonable for static availability.** Does not exercise drawing/share dependencies. Prefer one representative read-only share/drawing smoke check if those failures matter; a constant health route adds little. | `worker/share.js:462`; `worker/share.js:560` |
| zds | `/xrpc/_health` | **Basic.** Actual handler returns version + constant ok; route naming does not make it dependency-aware. Add a known public repo/blob read or storage readiness check if needed. | `src/http/server.zig:209` |
| birds.place | Website | **Basic.** Page availability does not establish watcher/index freshness or successful sightings reads. Add a bounded data-path check. | `worker/index.ts:1632`; application routes around `1783` |
| strata | Website | **Basic.** Progress/collections APIs exist; check their data freshness or storage readiness rather than the shell. | `src/index.ts:358` |
| relay | Indigo health, Grafana health, listReposByCollection | **Partial.** Real XRPC route exercised, but body and ingestion freshness unvalidated. Check useful query output and stream progress; Grafana health is not relay health. | Evergreen `site/services.json:959`; relay runtime implementation not fully verified |
| relay-eval | Website root | **Basic; richer evidence exists.** `/api/status` computes coverage over 24 runs but returns JSON findings. Check evaluator freshness and interpret coverage separately from evaluator liveness. | `relay-eval/src/server.zig:774` |
| zlay | `/_health`, Grafana | **Partial: DB readiness.** Add `/_healthz` for process-wide ingest stalls; keep DB and ingest checks separately named. | `src/main.zig:190` |
| coral | Backend `/health`, frontend | **Good progress check, bounded scope.** Health detects stale/dead Jetstream subscription and watchdog exits. Does not prove graph correctness or downstream delivery; preserve it and add outcome checks only for demonstrated gaps. | `backend/src/health.zig:53`; `backend/src/main.zig:199` |
| find-bufo | Search site and bot root | **Basic.** Bot stats server can keep serving while consumer/posting loop wedges. Add work-aware bot health with expected-idleness handling. | `bot/src/stats.zig:824`; `bot/fly.toml:11` |
| phi | `/health`, docs | **Good progress check, bounded scope.** Poll completion/staleness and watchdog are meaningful. Does not prove successful agent runs or tool outcomes. Track expected work completion separately if that is the concern. | `src/bot/main.py:197`; `src/bot/core/watchdog.py:26` |
| prefect | API health, Grafana, discovery pool | **Partial.** Does not establish worker execution or output freshness. Reconcile scheduled fleet coverage first, then check due work/outputs rather than only API liveness. | Live deployment/run above; pinned `flows/fleet_health.py:55` |
| PDS | Stock `/xrpc/_health` | **Contract unverified beyond reachability.** Local repo packages stock PDS and cannot establish its full health semantics. Add a known public record/blob read for data-path coverage. | `pds-infra/README.md:3`; `fly.toml:32` |
| pdsx | MCP initialize POST | **Partial request shape, unvalidated result.** A JSON-RPC error or wrong response with HTTP 200 is green. Validate protocol negotiation; no mutation probe needed. | Evergreen `worker/src/index.ts:34`; `site/services.json:1428` |
| pollz | Backend `/health`, frontend | **Basic.** Constant health response despite separate DB/Jetstream startup. Check DB readiness and consumer progress. | `backend/src/http.zig:157`; `backend/src/main.zig:24` |
| music-feed | `/health` | **Unknown contract.** Live response is ok; inventory has no repo. Locate source before claiming ingestion/freshness coverage. | Inventory entry; live body |
| at-me | Website | **Basic, reasonable for static availability.** Browser/PDS/guestbook functionality untested. Optional asset or representative read check, not a new constant health route. | `src/view/atproto.js:24`; `src/view/guestbook-state.js:12` |
| status | Website | **Basic; health route exists.** Fly uses `/_health`, which was reachable; inspect its actual dependency contract before claiming a stronger check by changing URL. | `fly.toml:22`; live `/_health` |
| evergreen | Website | **Basic self-site check.** Does not establish monitor Worker availability. Validate `/status` externally, including inventory coverage and freshness; avoid recursive self-probing. | `worker/src/index.ts:208`; `site/checker.js:3` |
| mcp-atlas | None | **Unmonitored by Evergreen; separate real crawl probes exist.** Check publication/projection freshness and nonempty expected coverage; a successful old crawl is not current health. | `flows/crawl.py:136`; `docs/operations.md:34` |
| pensieve | Website | **Basic.** `/health` is also constant ok. Per-user build/status and stale-index evidence exist; use aggregate stuck-build evidence or a bounded read, not merely a URL swap. | `src/worker.js:79`; `src/build.js:43`; `src/worker.js:150` |
| noti | Website | **Basic; scheduled refresh evidence exists.** Check last sweep/queue age and failures without exposing account data. | `src/worker.ts:918`; `wrangler.jsonc:61` |
| punch | None | **Coverage gap for a live indexer.** Already records knot cursor, last drain/error and publication timestamps. Evaluate overdue work from those fields. | `worker/src/index.ts:160`; `worker/src/index.ts:182` |
| bisk | Website | **Basic.** Dynamic top endpoints and snapshot workflow are outside the homepage check. Check snapshot age and representative data read. | `functions/top/market.js:1`; `functions/top/recommend.js:1` |
| brand | Website | **Basic.** Stateless resolver relies on upstream subrequests. A fixed read-only resolution canary adds value; another constant health route would not. | `src/worker.ts:14`; `src/worker.ts:109` |
| simmer | None | **Mostly client/static metadata.** No demonstrated server background-work health gap. Optional metadata availability; client sync diagnostics are a separate concern. | `wrangler.jsonc:3`; `src/diagnostics.ts:4` |
| race38 | Website | **Basic; rich progress evidence exists.** Health data includes cursor age, receive idle age, recovery, connection state. Use those verdicts/ages; do not assume its HTTP status fails on stale progress. | `worker/index.ts:64`; `worker/index.ts:97` |
| after-hours | None | **Config health exists, not outcome proof.** `/health` returns authorization mode/kill-switch flags, always 200. Monitor documented authorization/cleanup failure signals if this service needs coverage. | `browser-worker/src/index.ts:153`; `browser-worker/OPERATIONS.md:65` |
| labelz | None | **Coverage gap; retirement under investigation.** Confirm intended service before adding monitor. If retained, check label-store/query/subscription operation; no application Fly check found. | `src/server.zig:1`; `fly.toml:6`; inventory purpose |
| porxie | None | **On-demand origin behind cache.** Cached blob success can mask origin failure. A bounded known-blob origin check may help, but avoid frequent probes that defeat intentional scale-to-zero. | `fly.toml:33`; `README.md:50` |
| waow.tech | Website | **Basic, reasonable for static site availability.** Source not located at inventory repo path; no background-work claim. | Inventory Pages resource |
| chicago.at | Website | **Basic.** Inventory includes check-in/proxy Workers not separately exercised. Verify representative read paths if those are operationally important. | `README.md:1`; inventory resources |
| spindle | None | **Process inventory is insufficient.** Check queue age and recent successful CI completion using existing Spindle telemetry. No need to invent an HTTP endpoint for systemd. | Inventory `spindle.service`; Tangled core README |
| analytics | None | **Scheduled-work coverage unverified.** Registration/failure alerts do not prove timely ingestion/transforms/briefing delivery. Check last expected output, including degraded states. | `my-prefect-server/prefect.yaml:150`; inventory workflow list |
| dev automation | None | **Mixed scheduled/on-demand work.** Check cadence only for scheduled watchers; check queue/stuck age for requested jobs. Do not flag an unused on-demand deployment as stale. | `my-prefect-server/prefect.yaml:371`; inventory workflow list |
| presence | None | **Output freshness unverified.** Track expected sample age and distinguish unavailable sensing from intentional absence. | Inventory phone-presence registration; local deployment manifest |
| lore | None | **Coverage unknown.** Worker listed; source describes extension/site. Identify public read path and state dependencies before adding checks. | `pi-extensions/README.md:25`; inventory lore-site |
| ken | None | **Intentionally suspended per inventory.** No outage inferred. Verify desired state before reactivation monitoring. | Inventory embed-on-pds suspended; `ken/README.md:1` |
| highlights | None | **Unverified static deployment.** Locate public route/source; basic availability may suffice unless generated content has a freshness promise. | Inventory bsky-highlight-reel Pages |
| mikenowack | None | **Unverified site deployment.** Locate public route and owner intent; no outcome contract established. | Inventory mikenowack resource |
| n8 feed | None | **Unknown source/contract.** Locate feed generator and test a representative feed result/freshness. | Inventory bsky-feed app |
| relay storage | None | **Storage resources, not app endpoints.** Resolve consumer ownership, then check through consuming app; avoid inventing HTTP health per bucket. | Inventory unverified R2 consumers |
| follower-weight | None | **Database resource, not app endpoint.** Resolve consuming application and desired state before assigning health expectations. | Inventory unverified Neon consumer |
| slides | None | **Static Pages deployment, source/route unverified.** Identify public route if availability monitoring is wanted; no evidence of a background-work requirement. | Inventory slides Pages |


## Source provenance

These are local inspection snapshots, not deployment attestations. Working-tree
changes were preserved. Bot became modified only by this survey document.

| Checkout | Branch | HEAD | Working tree |
| --- | --- | --- | --- |
| [plyr.fm](/Users/nate/tangled.org/zzstoatzz.io/plyr.fm) | `main` | `1ea32ebd` | clean |
| [typeahead](/Users/nate/tangled.org/zzstoatzz.io/typeahead) | `main` | `5f4c42a` | clean |
| [pub-search](/Users/nate/tangled.org/zzstoatzz.io/pub-search) | `main` | `a80fec8` | modified |
| [stream](/Users/nate/tangled.org/zat.dev/stream) | `main` | `2c5b724` | modified |
| [rally](/Users/nate/tangled.org/zzstoatzz.io/rally) | `main` | `a1fd2a7` | clean |
| [doodl](/Users/nate/tangled.org/zzstoatzz.io/doodl) | `main` | `099fb38` | clean |
| [zds](/Users/nate/tangled.org/zzstoatzz.io/zds) | `main` | `96a7441` | clean |
| [birds.place](/Users/nate/tangled.org/birds.place/birds.place) | `main` | `d35d1bc` | clean |
| [strata](/Users/nate/tangled.org/zat.dev/strata) | `main` | `772bbdb` | modified |
| [relay](/Users/nate/tangled.org/zzstoatzz.io/relay) | `main` | `67465b2` | clean |
| [zlay](/Users/nate/tangled.org/zzstoatzz.io/zlay) | `main` | `41b950c` | clean |
| [coral](/Users/nate/tangled.org/zzstoatzz.io/coral) | `main` | `9ef7844` | clean |
| [find-bufo](/Users/nate/tangled.org/zzstoatzz.io/find-bufo) | `main` | `9535a08` | clean |
| [bot](/Users/nate/tangled.org/zzstoatzz.io/bot) | `main` | `f1f2f63` | modified |
| [my-prefect-server](/Users/nate/tangled.org/zzstoatzz.io/my-prefect-server) | `codex/operator-docs-cleanup` | `1c269fe` | clean |
| [pds-infra](/Users/nate/tangled.org/zzstoatzz.io/pds-infra) | `main` | `f382132` | clean |
| [pdsx](/Users/nate/github.com/zzstoatzz/pdsx) | `codex/record-page-cursors` | `6d0ca23` | clean |
| [pollz](/Users/nate/tangled.org/zzstoatzz.io/pollz) | `main` | `001a5c8` | clean |
| [at-me](/Users/nate/tangled.org/zzstoatzz.io/at-me) | `main` | `be6e421` | clean |
| [status](/Users/nate/tangled.org/zzstoatzz.io/status) | `main` | `04daa30` | clean |
| [evergreen](/Users/nate/tangled.org/zzstoatzz.io/evergreen) | `main` | `fec9f92` | modified |
| [mcp-atlas](/Users/nate/tangled.org/zzstoatzz.io/mcp-atlas) | `main` | `e05b0b4` | modified |
| [pensieve](/Users/nate/tangled.org/zzstoatzz.io/pensieve) | `character-memory` | `d1cf309` | clean |
| [noti](/Users/nate/tangled.org/zzstoatzz.io/noti) | `main` | `74c0a25` | clean |
| [punch](/Users/nate/tangled.org/zzstoatzz.io/punch) | `main` | `aff2398` | clean |
| [bisk](/Users/nate/tangled.org/zzstoatzz.io/bisk) | `main` | `6a6cc76` | clean |
| [brand](/Users/nate/tangled.org/waow.tech/brand) | `main` | `c5b2427` | clean |
| [simmer](/Users/nate/tangled.org/zzstoatzz.io/simmer) | `main` | `6aa94db` | clean |
| [race38](/Users/nate/tangled.org/zzstoatzz.io/race38) | `main` | `20f8490` | modified |
| [after-hours](/Users/nate/tangled.org/zzstoatzz.io/after-hours) | `main` | `7ccae54` | clean |
| [labelz](/Users/nate/tangled.org/zzstoatzz.io/labelz) | `main` | `4d057cc` | clean |
| [porxie](/Users/nate/tangled.org/zzstoatzz.io/porxie) | `main` | `032d095` | clean |
| [site](/Users/nate/tangled.org/chicago.at/site) | `main` | `bded7ff` | clean |
| [pi-extensions](/Users/nate/tangled.org/zzstoatzz.io/pi-extensions) | `main` | `ca518af` | clean |
| [ken](/Users/nate/tangled.org/zzstoatzz.io/ken) | `main` | `35110d6` | clean |

Spindle source was inspected separately at Tangled core `9e8b8f5` on
`nate/fluid-punchcard`. Projects with no source identified are explicitly marked
in the matrix. Source links in the matrix resolve relative to the corresponding
checkout above; the scheduled fleet analysis uses the deployed pin, not its local HEAD.

## Evidence and limits

The [live sweep evidence](evidence/evergreen-health-2026-09-20.json) preserves
the monitor result and selected deployment/run identifiers. No authenticated
user action, upload, publication, or synthetic job was triggered. A single
all-green sweep cannot establish sustained availability, and the source survey
is not a full review of each dependency or each external alert configuration.
