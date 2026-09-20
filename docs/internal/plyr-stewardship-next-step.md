# Next expansion: a plyr.fm evidence packet

Status: deferred behind [operator interaction design](operator-interaction-design.md),
per Nate’s 2026-09-19 direction. Retained implementation scope; not deployed or dispatched. Based on the
[2026-09-19 inventory](plyr-stewardship-2026-09-19.md). This is the next small
Gardener/stewardship expansion: monitor an existing project more meaningfully.

## Outcome

Phi can answer “what do we actually know about plyr.fm right now?” from one
bounded, attributable packet, without interpreting a website 200 as full health
or a partial cost estimate as an invoice. Gardener investigations can reuse that
packet with its source URLs and timestamps instead of rediscovering the service.

Extend my-prefect-server's existing `fleet-health` flow and its existing artifact/
finding delivery path. Reuse the costs producer and public plyr stats exporter;
do not introduce a scheduler, second cost collector, general service registry,
new credentials, or autonomous workflow dispatch. First verify the exact existing
artifact/event consumer before connecting the packet to Phi; use her existing
context/alert entry point, with facts as context rather than instructions.

Before choosing collection changes, reconcile Evergreen’s existing
`site/services.json`, `/status` worker checks, and resource-based cost attribution
with fleet-health and the hub. Reuse the public facts contract so Evergreen and
Phi do not develop competing inventories or freshness claims.

## Small data contract

One `plyr.fm` record with:

- Observation timestamp and source URLs; per-observation status `observed`,
  `missing`, `stale`, or `failed`. Preserve the difference between a timeout,
  invalid JSON, missing key, and a valid zero.
- Frontend reachability; API reachability; a database-backed `/stats` observation;
  labeler reachability. State exactly what each probe exercises.
- Costs: hub `generatedAt`, dashboard `generated_at` and `infra_as_of`, integer
  cents by provider and combined estimate, estimation flags, and explicit coverage
  limitations (Neon overage, unattributed R2, other unmeasured usage). No double
  counting between hub and dashboard. A missing provider is unknown, not free.
- Static capability facts linked to reviewed source: GitHub development source,
  Tangled mirror role, investigation support, proposal support unverified/unsupported,
  and release triggers. Model scores never override these facts.
- Links to full evidence. Keep a compact rendered context within 2,000 UTF-8 bytes;
  prioritize failures, freshness and caveats over cumulative totals if space runs
  out. Preserve full structured observations in the existing artifact.

The resource count is fixed: existing frontend GET plus API health, API stats,
labeler health, and cost dashboard. Reuse the flow's hub fetch if it exposes the
body; otherwise add one hub GET. No writes, synthetic uploads, authentication
flows, PDS mutation, or audio processing in the sweep.

## Acceptance criteria

1. A live read-only observation reproduces the distinction between a reachable
   frontend/API and unknown upload/queue/ingestion health. A failed DB-backed
   read cannot leave the service labeled wholly healthy.
2. Using the retained 2026-09-19 public snapshot, code derives $65.37 infrastructure
   plus $5 AudD = $70.37 estimated total; preserves 08:00 infrastructure freshness
   separately from 20:05 export freshness; does not assert current invoice accuracy.
3. Freshness is calculated in code. Start with explicitly documented thresholds
   of 30 hours for the daily infrastructure feed and 3 hours for the hourly
   dashboard, allowing schedule delay. Treat future/invalid timestamps as unknown.
   These are proposed monitoring tolerances, not measured service SLAs.
4. Test meaningful failure modes against captured payloads and real parsing:
   timeout, malformed data, missing provider, zero usage, stale upstream behind
   fresh export, partial probe failure, and divergence between cost feeds. Exercise
   the HTTP adapter against a controlled local server; run one bounded live read
   to verify the actual payload contract. No model or publishing calls required.
5. Reuse existing unhealthy-finding semantics. Identical observations do not
   cause repeated investigations or notifications; a meaningful failure/recovery
   is identifiable. Verify the existing delivery/deduplication path before deciding
   whether any new state is needed. No new public posting path.
6. The compact packet stays within 2 KB and links full evidence. Report added
   request count, response bytes and wall time against the existing shallow check.
   Bound each request to the existing 10-second timeout and at most one retry;
   bound total added check time to 60 seconds. A slow source yields a failed
   observation, not an unbounded sweep. No paid classification dependency.
7. Phi/Gardener can answer from the packet: which checks worked, what remains
   unknown, how old the costs are, and whether a proposal route exists. Validate
   those answers manually against the full observations before rollout.

## Forge prerequisite and authority

Do not route a plyr.fm patch through Tangled because it appears in the front-door
allowlist. Before a later proposal milestone, reconcile per-workflow repository
capabilities with deployed schemas and verify the bridge's deployment IDs/pools.
A GitHub proposal path needs explicit identity/credential design and operator
review; this monitoring expansion does not add one.

Work for this packet belongs in my-prefect-server, which already has a Tangled
maintenance path. Its own merge/deploy rules still apply. Implementation can be
reviewed locally without publishing, dispatching Gardener, or modifying production.

## Rollout and recovery boundaries

Capture an offline before/after packet and the bounded live-read measurement.
Then review the actual diff and existing delivery integration before deployment.
No service configuration, budgets, permissions, or proposal publishing change.
If the enrichment misbehaves, disable/revert the plyr-specific enrichment and
retain the existing shallow check; preserve evidence and label lost coverage
rather than silently calling it healthy. Existing artifacts are historical facts,
not instructions to retry an operation.

Success is better attributable service knowledge and fewer repeated discovery
reads—not a claim of lower infrastructure spend or successful self-improvement
before a later maintenance change is measured.
