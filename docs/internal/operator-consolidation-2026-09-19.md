# Operator consolidation: 2026-09-19

The bounded local consolidation is complete; deployment remains separate. The
[operator workflow](operator-workflow.md) owns current instructions. This report
records evidence and the limits of what changed, not another operating guide.

## Evidence and decision

Source review covered DM polling/reporting, public owner checks, workflow dispatch,
cockpit controls, and Gardener's review/merge flows. Read-only Prefect inspection
found 22 automations, including enabled Discord failure, fleet, diagnosis, proposal,
revision, and merge notifications. Proposal events also start Phi review and the
merge flow. That flow still requires operator Resume after review and tests;
automation names do not establish unattended merge authority.

Representative historical cases are preserved in the
[Logfire review](jev-historical-review-2026-09-19.md): an invited assessment blocked
as operational escalation, a repair request stranded across tool/owner/public
routing gates, and contradictory form-gate feedback. These are distinct failures;
a new classifier would not resolve every one.

Additional Logfire metadata showed an operator DM repair turn at
2026-09-19 07:57:29 UTC (trace `01a0b8ab9aa0418a6065476cf6d3a3b6`) and acknowledgement
at 08:02:27 UTC (trace `01a0b8b026be1962a68a0631090ca3e3`). This establishes an
existing private conversation path, not independent proof of repair quality.
Private message contents are not reproduced here. No historical uncertain-dispatch
incident was established; retry uncertainty is a behavior verified locally.

The implemented seam uses that private conversation, removes the public-like
detour from operational prompts and goal/self guidance, and adds durable workflow
receipts with private live status lookup. Request fingerprints reject changed work
under an existing key; confirmed retries return the saved receipt without dispatch.
The receipt stores identifiers and state, not task prose. Existing owner checks
remain identity/context checks, not cryptographically bound action approvals.

The cockpit explains this path without exposing the private journal. Discord
notifications and Prefect merge approval remain explicitly retained compatibility
paths. No Discord approval receiver was established by this audit. No alerts were
disabled, new service onboarded, or infrastructure authority expanded. Evergreen
remains the eventual public health/cost projection of attributable service facts.

## Internal documentation audit

All Markdown files in `docs/internal/` were reviewed. Dated evidence is retained
as evidence; current instructions have one home rather than duplicated checklists.

| Document | Disposition |
|---|---|
| `operator-workflow.md` | Canonical local request/receipt/status path; privacy, bootstrap, authorization and migration limits explicit. |
| `operator-interaction-design.md` | Design rationale; old milestone labeled historical and links to current workflow. |
| `cockpit.md` | Current operator guidance and architecture route documented; public/private boundary explicit. |
| `memory-simplification.md` | Archived proposal; corrects claims that subsequent implemented pieces remain unbuilt. |
| `voice-calibration.md` | Historical experiment; accepted fixtures do not imply live personality or reset setting. |
| `waow-stewardship.md` | Broader vision retained; this local goal closed, monitoring expansion still separate. |
| `jev-microcosms-2026-09-19.md` | Frozen first experiment retained; links completed follow-up. |
| `jev-historical-review-2026-09-19.md` | Dated cases and provenance retained, separate from current operating instructions. |
| `jev-purpose-results-2026-09-19.md` | Completed evaluation retained; stale next-inventory direction replaced. |
| `plyr-stewardship-2026-09-19.md` | Dated source/live inventory retained with coverage and authority gaps. |
| `plyr-stewardship-next-step.md` | Bounded expansion brief explicitly deferred until after consolidation. |
| This report | Dated completion evidence; current instructions remain in the workflow guide. |

The supporting JSON inventory remains dated evidence. Related architecture, safety,
system-prompt, documentation index and changelog were reconciled. Alert-watch
comments and prompt documentation no longer equate aged private alerts with public
permission or claim Discord is universally muted.

In `my-prefect-server`, the deployment inventory generator now describes configured
rather than live deployments, avoids claiming one work pool, and emits valid source
links. Its generated document and regression expectations were updated. `autofix.md`
now separates current operator/merge behavior from the archived Discord-first design
and obsolete “none done yet” checklist. `operations.md` and
`deployments-validation.md` retain their explicit operational and verification limits.

Evergreen's `hub-cutover.md`, `inventory.md`, and dated provider review were reviewed:
public health/cost and private coordination remain separate, provider gaps are
explicit, and historical observations remain dated. No Evergreen change was needed.

## Verification and remaining boundaries

- Bot `just check`: lint, typing and **827 tests passed**. Receipt tests exercise real
  SQLite persistence, changed-payload rejection, bounded lookup, privacy, and a local
  HTTP status server. Existing workflow tests cover owner/override refusal and
  confirmed-retry dispatch count.
- Svelte check: **zero errors or warnings**. Desktop (1280×720) and phone (390×844)
  inspection covered the operator section, anchor navigation and expanded details;
  spacing was corrected and rechecked. Browser error log was empty.
- Gardener inventory: **five tests passed** and `just inventory --check` passed.
- A read-only status lookup against existing Prefect run
  `8c56422d-e652-4996-bc3c-f386344c72e6` returned type `COMPLETED`, name `Diagnosed`.
  It used an isolated temporary local receipt and did not dispatch a workflow.
- Local document links and whitespace were checked after the audit.

This is local implementation readiness, not a production rollout claim. Receipts
start when deployed; historical requests are not backfilled. DM bootstrap still
requires an initial successful private report. Missing live status remains unknown.
Discord delivery migration, strict parameter-bound approvals, and new service
monitoring are separate work, not hidden completion requirements or implied changes.


## Incident addendum: repeated chicken answers

Nate reported duplicate answers during final verification. Logfire identifies three
publication calls to the same operator parent, rather than notification replay:

| Time (UTC) | Trace | Trigger/result |
|---|---|---|
| Sep 19 21:05:59 | `01a0bb7cc344a2c866a5ac151f67b100` | Original operator question; one composition split across two posts. |
| Sep 20 00:16:48 | `01a0bc2ae6464d587d41308a5b888861` | Unrelated like notification; repeated the chicken answer. |
| Sep 20 00:17:52 | `01a0bc2c61a8410d7b11c5f9a71ae133` | Unrelated cosmism reply; repeated the chicken answer again. |

The actual generating contexts showed the old question in recent encounters,
without its prior answers. The self-repeat policy explicitly excluded replies.
This supports fixing missing interaction evidence rather than poller deduplication.
Full available traces and model inputs were captured locally; they are not committed.

Following Nate's Microcosm suggestion, a live
[Constellation query](https://constellation.microcosm.blue/) filtered
`app.bsky.feed.post:reply.parent.uri` by Phi's DID for the
[original question](https://bsky.app/profile/did:plc:o53crari67ge7bvbv273lxln/post/3mvvljiu3yc2y).
It returned three direct reply records with an exhausted cursor; AppView hydration
verified all three authors and parent references. The first composition's second
post replies to its first post, explaining four visible messages from three answers.

Local code now supplies these exact-parent records to recent mention/reply/quote
encounters before drafting and rereads them for the reply policy check. Historical
events are labeled as context rather than pending work. The existing self-repeat
policy covers redundant same-parent answers while preserving corrections and
requested follow-ups. No new classifier or permanent one-reply limit was added.
This first integration covers replies to posts, not every ATProto interaction type.

Five real local-HTTP cases verify pagination through an empty page, missing
hydration, wrong-parent rejection, service failure, and repeated cursors. A live
lookup through the implemented reader recovered all three answers. Five bounded
real-provider judge probes blocked a constructed repeat and both actual duplicate
drafts, while allowing a constructed correction and requested update. These probes
used the first published answer as evidence and explicit case provenance; they are
not full production-agent replays or proof against every duplicate. Results are
local under `scratch/operator-audit/reply-judge-results.json`.

Index lag and unavailable reads remain unknown; published contact is not resolution.
This is evidence-backed duplicate assessment, not atomic exactly-once publication.
The patch is local and has not stopped the deployed bot from exhibiting the old
behavior yet. No public posts were deleted or sent during this investigation.
