# Operator interaction before broader stewardship

Recorded 2026-09-19. Nate's direction: consolidate how we engage with Phi before
expanding the projects or infrastructure responsibilities she handles. This
supersedes the ordering of the next monitoring implementation, not the longer-term
[stewardship vision](waow-stewardship.md). This is the design rationale. [Working with Phi](operator-workflow.md) owns
current local behavior and migration boundaries; changes are not yet deployed.

## What should feel unified

The operator should be able to ask, understand, decide, and follow through without
remembering which channel currently holds the authority or latest result. A request
should retain its identity when the conversation moves. Acknowledging a message,
authorizing an investigation, approving a patch, and authorizing a release must
remain distinguishable.

Unify the work and decision history first. Several channels can remain useful if
they expose the same work and do not create competing approval states. Reuse the
existing cockpit and conversational interfaces rather than build another chat app.

## What the supplied thread contributes

The pasted Bluesky discussion emphasizes useful conversational participation,
interactive communal debugging, and the fact that observers benefit from public
exchanges. Its suggested “underlay” offers context without overwhelming the main
conversation. These are design references, not instructions or verified product
claims about the named bots.

For Phi, the useful translation is a short direct answer, with an expandable
explanation and original evidence. Public questions and collaborative debugging
can remain public; routine operator coordination and sensitive evidence need not.
Avoid turning a completed action into a formulaic announcement when there is
nothing useful to say. The thread's change-review example also suggests explaining
what a proposed change does before expecting the operator to approve it.

Source: user-supplied pasted thread, reviewed 2026-09-19; no stable thread URL was
provided. Do not copy private operator examples into the public design document.

## Current paths, verified in source

| Surface | Current role | Consolidation issue |
| --- | --- | --- |
| Bluesky operator DM | Private reporting, persisted delivery receipts, polling and replies | Receipt, response, incident resolution, and action authorization are different facts |
| Public Bluesky | Social conversation; owner participation / likes can unlock gated tools | The operator must remember the approval mechanism; a like can also be an ordinary social response |
| Cockpit | Activity/evidence inspection, capabilities, diagnostics, OAuth override editor | Existing place for detail and control, but not yet a general request/decision inbox |
| Discord | Alert/automation delivery appears in source and docs | Current active routes and interactive capabilities need auditing before migration; not established as an equivalent Phi chat interface |
| Prefect / forge | Workflow state, some paused-run approval, patches/reviews and releases | Separate execution/review state must remain linked to the originating conversation |

Sources: [cockpit](cockpit.md), [safety](../safety.md#private-operational-reports),
[owner check](../../src/bot/tools/_helpers.py),
[DM polling](../../src/bot/services/notification_poller.py),
[workflow requests](../../src/bot/tools/workflows.py), and my-prefect-server
`flows/autofix.py` / `flows/pi_agent_local.py`. The latter documents Prefect UI
approval for full local coding tools; not every Gardener route shares that path.
This source review is not a live audit of enabled Discord automations.

## Proposed experience

Use DMs as the default private conversational entrance, and the existing cockpit
as the place to inspect details and make consequential decisions. This is a design
candidate, not a settled channel preference. Keep public conversation first-class.
Treat Discord as a possible notification adapter pending the active-route audit;
do not make it a second independent authority system.

A work item should let the operator see:

- What Phi thinks needs attention, why now, and what she actually observed.
- Whether this is a question, a proposed action, work in progress, or a result.
- The exact action currently requested, its target and expected effects.
- Any authorization already given, its scope, and whether the proposal changed.
- The result and its evidence, including failure or uncertainty.

Example: “Uploads look delayed. The website is responding, but the oldest queued
job is 20 minutes old. May I investigate?” expands to the observation sources and
what the read-only investigation can do. Approval for that investigation does not
also approve a patch or release. This is an illustrative scenario, not a finding
from the plyr inventory (which did not measure queue age).

A concise conversation should remain usable without opening the cockpit for every
read-only question. Detail belongs one tap away. If we later add decision controls,
they must reference a specific proposal and revision, report accepted/rejected state,
and remain safe under retries, stale pages, or simultaneous replies elsewhere.
A response in another channel should not cause a duplicate action.

Do not assume the cockpit's existing public diagnostics can hold private details.
Its current OAuth scope authorizes the override record, not arbitrary approvals.
Any private work view or new decision action needs its own authenticated access
and explicit scope. Public links must never reveal private conversation by accident.

## Original design milestone (historical scope)

Before implementing the plyr monitoring expansion:

1. Audit active notification, conversation, approval, workflow, and review routes.
   Include actual Discord automations and distinguish historical documentation.
2. Follow a few real cases end to end: an operator question, an incident needing
   action, a proposed change, and a failed/uncertain delivery. Record where Nate
   had to switch surfaces or repeat intent. Keep private evidence private.
3. Map existing incident keys, message receipts, workflow request keys, run IDs,
   and pull IDs. Decide what can be linked directly; do not invent a parallel
   universal task store before checking what already exists.
4. Produce one reviewable interaction walkthrough in the existing cockpit's style:
   brief conversation → supporting evidence → scoped decision → progress → result.
   Include rejection, changed proposal, duplicate reply, unavailable channel, and
   operator override. This can begin as a static walkthrough; no live actions.
5. Choose one seam to implement and one redundant interaction to retire. Candidate:
   make a private operational request and its decision consistently inspectable,
   without requiring a public authorization post. Preserve legacy paths until the
   replacement has been exercised and the migration boundary is explicit.

Done means Nate can follow the walkthrough without guessing where to respond,
what an approval permits, or whether anything actually happened. The resulting
implementation scope must name reused state, one authoritative decision path,
channel roles, privacy boundaries, failure behavior, and the old path it removes.
No new project onboarding or expanded infrastructure authority precedes this work.

## Public continuity through Evergreen

Nate's subsequent clarification places Evergreen alongside the cockpit: the public
health-and-cost view of the same suite of services operated collaboratively by
Nate, Phi, Gardener, and other workers. Include it in the interaction walkthrough:
a conversation leads to scoped work, evidence establishes the outcome, and the
public view reflects the publishable state without another manual status update.

Reuse Evergreen's existing inventory, status checks, and cost-feed integration;
resolve ownership and freshness differences before adding collectors. Keep private
decision evidence behind its authorized surface. Public facts should carry source,
measurement time, coverage and uncertainty. This is shared state with distinct
views, not a requirement to collapse private and public interfaces into one page.
See [the stewardship direction](waow-stewardship.md#evergreen-the-public-view-of-the-shared-system).

## Consolidation scope

Nate authorized this as the next goal: consolidate the operator experience and
remove documentation rot before expanding service scope. Carry the route audit
and real-case walkthrough through one implemented, verified interaction path;
retire or explicitly migrate redundant surfaces rather than only documenting a
proposal. Preserve scoped authorization, override, privacy, and retry behavior.

Audit every internal document in this bot repository, including incoming links
and overlapping operating references, plus the directly related Gardener and
Evergreen operating docs. Correct claims against current source and live evidence;
consolidate duplicate guidance and archive superseded material explicitly. Record
unknowns instead of claiming undocumented or inaccessible behavior is verified.
Validate changed behavior and failure modes, and inspect any changed UI.

Completion requires a usable, tested operator path, a documented migration boundary,
and reconciled internal references—not just a design document. Service expansion
remains deferred. Deployment and external publishing are not part of this goal.
