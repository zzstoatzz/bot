# Safety boundaries

Phi's policies, authorization checks and operator override are separate
boundaries. This reference describes the implemented routes. The original
incident below explains why an independent judge exists.

## Policy and public delivery

`core/policy.py` owns `POLICIES` and the actor's `POLICY_SUMMARIES`. The current
policy slugs are listed in [system-prompt.md](system-prompt.md); adding one must
update the typed verdict, summaries and drift-checked reference. The judge is
configured independently from the author; see [models](architecture.md#models-and-cache).

Publication adapters supply the proposed action, code-derived contact evidence,
current conversation, relevant prior coverage and risk metadata. The author
cannot grant itself authorization by asserting provenance in tool arguments.
Verdicts allow, warn or block. A refusal returns its reason; composed public
communication fails closed when the judge is unavailable. Public-form and
phrasing rules live in `core/etiquette.py` and the shared scoped Humanizer skill;
[public delivery](public-etiquette.md) describes their current contract.

| Route | Implemented boundary |
|---|---|
| `post` | Verified targets, contact authority, mention consent, mute checks, prior coverage, whole split preview, policy judge and operator override |
| `publish_blog_post` | Operator override, policy judge with received context, document validation and duplicate-title check; revisions require the read CID |
| `write_bio` | Operator override and profile-description policy review |
| PDSX like/repost creation | Verified target, own-post refusal, policy review and current thread mute check; subject CID is completed by the guard |
| PDSX feed-record deletion | Own-record verification, policy review and operator override; deletion fails closed when judgment is unavailable |
| Other-app post/reaction/profile records | `core/app_records.py` maps supported shapes to the corresponding public-action checks |
| Repository comments/issues/pull prose | MCP guard supplies repository context to the public-composition judge |
| Private operator delivery | Override, policy review, private conversation evidence and idempotent delivery receipts |

The public-form rule does not govern likes, deletions or private memory, but that
does not exempt those actions from their other checks. Retraction remains a
capability: the August 19 change replaced a blanket raw-delete refusal with a
governed path. A boundary must not leave Phi able to publish but unable to retract.

## MCP mutation guard

`core/mcp_tools.py` attaches `make_mcp_guard` to every server. The guard in
`core/mcp_guard.py` first routes protected record collections to their trusted
native tools, then checks the operator override for mutations and records
provenance. Raw composed feed posts cannot bypass `post`. Reactions and
retractions have governed routes rather than a blanket feed-write prohibition.

Unknown verbs count as mutations. Reads pass through under the override. Semble
method calls are classified by their SDK method; legacy code-mode execution is
also recognized. Library mutations are serialized in-process and reconsidered
against refreshed library context when another run changed it. That is local
coordination, not a distributed lock across external writers.

## Operator override and runtime pause

`io.zzstoatzz.phi.override/self` lives on the **operator's** PDS, selected by
`settings.owner_did`. The cockpit's `/operator` writes the signed-in operator's
record. Repo ownership establishes authority; Phi's copy has no effect.

`core/override.py` caches it for 60 seconds. Fetch failures retain the last known
state. Before any successful fetch, unavailable state is treated as inactive;
this is a deliberate availability tradeoff, not fail-closed boot behavior.
An active override supplies a context banner and the operator's refusal message.

All MCP mutations and the native publication, personality, workflow, trading and
private-delivery routes check this control. It also prevents dispatch of operator
DM runs. Native goal, SELF, persona, follow, profile-label and mention-consent
writes observe the same override; their existing owner and validation contracts
still apply when it is off. Reads, SELF's initial review, private memory and
private thread mutes remain available. Runtime pause and `VOICE_RESET` separately
prevent normal run dispatch. Do not describe safe mode as preserving an outbound
PDS-note or DM escape channel: those delivery routes are gated.

The July 25 generalized MCP guard closed gaps in Semble/Tangled mutations and
raw deletes. September 5 (`6867786`) added the native blog override check. The
former claim that blogs are deliberately unjudged or ungated is obsolete.

## Invariants when changing these boundaries

- Preserve computed provenance, exact targets and explicit failure states.
- Keep actor instructions and independent enforcement aligned without treating
  one as a replacement for the other.
- Preserve retraction, correction and explicit read routes when consolidating.
- Keep private message bodies out of public evidence and public journals.
- Test the actual write boundary and failure behavior, not just prompt wording.

## the incident that shaped this

on 2026-06-30, ~3.5 hours after a model upgrade (sonnet-4.6 → sonnet-5),
a scheduled cycle replied to a stranger's post found via the discovery
pool. nobody had invited phi into that thread. nothing malfunctioned:
no rule anywhere said "don't reply uninvited" — the previous model
simply never did it, and several surfaces (the posting tool's docstring,
the discovery pool's "warm leads" framing, phi's own stated plans)
quietly pointed toward the behavior. the restraint we'd been relying on
was a property of the model, not of the system, and it didn't survive
the swap.

the design conclusion: norms that matter must be (a) written down and
(b) checked by something other than the model that wants to act.
phi's own write-up: ["The Instruction I Wrote For Myself"](https://greengale.app/phi.zzstoatzz.io/3mpn7xbmozf22).


## Directed contact

`uninvited-reply` remains the historical journal key, but its scope is directed
contact, not a particular post format. Publication adapters pass verified
`ContactTarget` destinations and evidence to `check_action`. Each destination
must have invitation, own-conversation, operator-account or specific operator
direction evidence before the model judge can permit publication. The judge
still checks that operator text actually authorizes the action.

Both parent and embedded-record destinations use the same check; permission for
one does not transfer to another. Discovery and bot labels supply no authority. A post linked from someone else's
notification is not an invitation from its author: it counts only as operator
direction when the operator's post is the one that links it.
Mention facets retain their consent allowlist. A top-level placement is not an
exemption. Independent writing without directed contact remains permitted.
Missing authority is recorded in the existing public revision journal and
returned to Phi before any post is written. Future delivery adapters must
report their contact effects to this boundary rather than add policy exceptions
for new interaction names.


## Private operational reports

Operational incidents requiring the operator's action use `report_operator`,
which sends a Bluesky DM only to the configured owner DID. The tool checks the
operator override and policy judge before sending. `/data/operator-reports.sqlite3`
records the incident opening, attempted delivery, conversation/message receipt,
and whether the operator subsequently responded. A send is reserved before the
network call; uncertain delivery is held for investigation, never blindly retried.
A reopened incident has a distinct identity. Private message bodies are not stored
in this journal or included in public-action evidence.

Both private-message tools require concise, plain-language communication about
the affected work and the operator's decision. The judge rejects diagnostic
dumps and unnecessary process narration, while allowing requested technical
answers. Before an unsolicited report, the judge reads the latest 20 private
messages to detect repeated requests even when the incident key changes. This
history stays in private moderation context; a failed read withholds delivery.

The public judge receives current delivery metadata. Six hours of unanswered
private delivery permits considering public escalation only while the incident
remains open and needs operator action. A response stops unattended escalation;
it does not resolve the incident. Failed or incomplete chat-history reads do not
prove silence. Explicit requests for public reports remain permitted. Normal
mentions no longer mark every incident visible to the run as notified.

`conversational-norms` applies alongside platform constraints and voice: contact
eligibility does not imply a response is wanted. The exact parent message and
complete split preview reach the judge. Behavioral refusal reasons survive the
voice-form check. `bluesky-guidelines` is a versioned, sourced operational digest;
it does not claim to reproduce all guidelines or identify proprietary detectors.


Operator DM replies are polled every 30 seconds from the existing one-to-one
conversation, starting when private reporting began. Incoming message IDs are
persisted after a successful run; pause/override prevents dispatch. The run uses
`process_operator_dm` and `reply_operator_dm`, with private context excluded from
the public notification/extraction pipeline and automatic episodic summaries.
Private conversations remain visible in authorized operational traces. Responses
are limited to one idempotent send per incoming batch. No response is required.

### Contact and retraction from a DM

A reply or quote made during an operator DM run carries the conversation as
its contact evidence, the same way an operator post in a batch does. That only
moves the decision from the hard block to the judge, which reads the DM and
decides whether the operator asked for this contact. The judge also reads the
DM for governed feed-record retractions through `delete_record`; those
retractions fail closed when the judge is unavailable.

### Blog invitation context

The blog gate receives the current incoming events, their authors, source URIs,
and thread context separately from the proposed article. Private operator
conversation is labeled private evidence. The judge decides whether a request
actually invites this article; an unrelated request in the same batch is not
authorization. GreenGale is identified as the publication surface. Privacy and
all other applicable checks still run, and judge failure still prevents public
publication. Scheduled runs without received context do not invent an invitation.

### Muted threads

`manage_account` exposes thread mute inspection, mute, and unmute using a post
AT-URI. The client resolves the root and verifies authenticated Bluesky state.
Every reply send, including subsequent parts of a split post, checks that state
again and refuses when muted or unavailable. This covers runs started before a
mute. Bluesky does not offer an atomic check-and-send: an external mute between
the final check and the write remains a race. A failure after earlier parts were
sent stops further parts; it does not retract those already published.

For a root created during the same split-post call, delivery retries unavailable
AppView state after 1, 2, 4, and 8 seconds. It still requires a confirmed unmuted
result. Exhaustion reports partial publication with the last published URI,
so the caller can inspect it instead of resending the whole draft.

### Reporting policy scope

The operator-reporting policy distinguishes requests for operator intervention
and incident reports from factual corrections and discussion of public work.
Infrastructure nouns alone do not turn a correction into an escalation; changing
those nouns or presenting an incident reminder as a personal lesson does not
make an otherwise blocked escalation acceptable. Privacy and contact rules
still apply to every draft.

Likes and reposts also check current thread mute state immediately before the
guarded record write, after policy approval. A muted or unavailable thread
refuses delivery. Removing an existing reaction remains permitted; this check
does not prevent disengagement.

## Private workflow receipts

`request_workflow` stores dispatch identity and confirmation in the existing private
operator journal. Reusing a confirmed key returns the recorded run; changing its
payload is refused. Unconfirmed delivery does not establish that no work started.
`operator_workflow_status` is available only in an owner DM, reads receipts and
current Prefect state, and cannot dispatch. No public cockpit endpoint exposes the
journal. It retains identifiers and an action fingerprint, not task prose. The
existing owner gate and operator override still govern new workflow requests.
See [operator workflow](internal/operator-workflow.md) for scope and migration limits.

## Repeated answers

Reply checks receive exact-parent published reply evidence through Constellation
(`reply.parent.uri`, filtered by Phi's DID), hydrated and identity-checked against
AppView. The existing self-repeat policy applies to redundant same-parent answers,
while allowing corrections and specifically requested follow-ups. Recent encounters
carry this evidence before drafting as well. Index lag, pagination bounds, and
unavailable records remain explicit; this is not an exactly-once publication lock.
The lookup discovers public interactions, not private decisions or task completion.
