# Working with Phi

Use the existing private Bluesky conversation for operational requests and their
follow-up. Public questions and communal debugging can remain public. The
[cockpit operator page](https://phi.zzstoatzz.io/operator) provides controls and
diagnostics; its “Work with Phi” section explains the path. The receipt lookup and
updated guidance described here are local changes pending deployment.

## Request, receipt, follow-through

1. Ask for a specific investigation or proposed change, naming the service and
   constraints. Phi can ask privately through `report_operator` with a `note:` key.
   Your private request does not need a public authorization post or like.
2. `request_workflow` checks owner participation and the override. It records the
   request key, action fingerprint, repo, workflow, source DM ID when present, and
   confirmation state in the existing private operator SQLite journal. It stores
   no task prose. The same key cannot silently change its work description.
3. A confirmed response contains the request key and run ID. Repeating the same
   request returns that receipt without another dispatch. If delivery is uncertain,
   the receipt stays unconfirmed; an explicit same-payload retry retains the
   bridge's idempotency identity. Never use a new key to bypass uncertainty.
4. Ask Phi for progress in the private conversation. `operator_workflow_status`
   looks up one request or the ten most recent local receipts and reads current
   Prefect state. It cannot start work. Missing credentials or a failed read return
   unavailable; a queued receipt is not a current run-health judgment.
5. Review the actual result and supporting evidence. `COMPLETED` can have a state
   name such as `Degraded`; neither completion nor Phi's summary proves a patch
   was merged or deployed. Existing forge review and operator-controlled merge/
   release mechanisms remain authoritative.

The receipt store begins with this change. Earlier work still needs its original
Prefect/pull link. It is a dispatch journal, not a second task system or approval
ledger. Run status and artifacts remain in Prefect; patches and reviews remain on
the forge. Request identity does not grant authority.

## Authorization and privacy

The existing owner check is unchanged. A direct operator-authored run is eligible;
a public batch containing an owner like/repost is eligible only without other
authors. This is an identity/context gate, not strict per-action approval binding.
Phi must interpret the specific operator request; unrelated conversation does not
authorize a mutation. New parameter-bound approvals are not implemented here.

Receipt lookup requires both owner participation and the private DM entry point.
No public endpoint exposes these records. Existing policy, override and publication
checks still apply. A private instruction to prepare a proposal is not permission
to publish unrelated private context. The operator override also stops DM polling;
new messages are not processed while it is active.

DM polling currently begins after the first successful private report. This is an
existing bootstrap constraint, not a promise that any first-ever DM starts a run.
Replies are one idempotent send per incoming batch; uncertain sends are held for
inspection. An acknowledgement is contact, not incident resolution or blanket
approval. See [safety](../safety.md#private-operational-reports).

## Migration boundaries

The retired detour is the instruction to post publicly and obtain a like when
an operator DM already authorizes the specific request. Goal and self-record tool
guidance now directs missing authorization requests to the private reporting path.
The legacy public owner gate remains available for existing conversations; it has
not been removed or weakened.

Discord remains a notification transport. The 2026-09-19 live audit found enabled
failure, fleet, diagnosis, proposal, revision, and merge notifications. No Discord
conversation/approval adapter was established by this audit. Do not turn Discord
reactions into authority or disable its alerts until replacement delivery has been
verified. Local guidance changes do not mean those automations were migrated.

The merge flow's Resume approval remains in Prefect after tests/review; its
credential stays with the trusted workflow. This consolidation does not move merge
approval into a DM or expose a new cockpit approval button. Some live routes differ
from configured routes, so verify the exact deployment before dispatch; see the
[plyr inventory](plyr-stewardship-2026-09-19.md#forge-execution-and-authority-boundaries).

Evergreen stays the public health/cost projection. It shares attributable service
facts, not private operator correspondence or authority. The cockpit's public
OAuth override editor likewise is not an authenticated private request inbox.
