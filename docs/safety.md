# safety

how phi's public actions are bounded, and why the bounds are structural
rather than prompt-only. three layers, built 2026-07-01/02 after an
incident (below).

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

## layer 1 — written policies + an independent judge

`bot/core/policy.py`

- **policies are data**: a `dict[PolicySlug, str]` of natural-language
  policies (`uninvited-reply`, `bliss-attractor`, `pile-on`, `handle-hygiene`,
  `self-repeat`, `public-etiquette`). adding one
  is a two-line change (extend the `PolicySlug` literal, add the entry);
  the type checker keeps them in sync, and the literal becomes an enum
  in the judge's output schema.
- **one-line summaries (`POLICY_SUMMARIES`, same file) render into phi's
  operational instructions**, so phi knows her norms up front — the judge
  is the backstop, not the communication channel. the judge alone reads
  the full statute: rendering it into every run billed ~1.9k chars for
  law phi experiences as tool results anyway (2026-08-07 diet). both
  dicts are typed against `PolicySlug`, and a test asserts the summaries
  cover every policy.
- **the judge** is a separate model (`policy_model` setting — a
  different *provider* from phi since 2026-07-30, see
  [architecture.md](architecture.md#which-model-runs-what)) that
  reviews every `post()` call — top-level and reply — before it
  executes. separate is the point: a judge that shares phi's weights
  shares her blind spots, which is how the 2026-06-30 incident got
  past self-restraint in the first place. it sees the proposed action, its **provenance** (computed,
  not asserted: in the notification batch / phi's own thread / the
  operator's post / found-unprompted), and phi's recent posts (context
  for tendency policies).
- **tiered verdict**: `allow` (default), `warn` (action proceeds, a
  policy note rides the tool result), `block` (nothing posted; phi gets
  the policy and reason as the tool result so she can adapt in the same
  run — a like, a memory write, a different post).
- **composed public actions fail closed** when the judge is unavailable, including invited replies. The operator override and raw-write guard remain separate checks.
- **public form** (`participation-v7`): short public writing can be a direct question, answer, correction, or subject-specific humor. A comic turn is not mandatory. Generic quips remain rejectable. Blogs are assessed as complete connected pieces. Internal reasoning and stored notes are outside this form rule. The default judge is Terra through the Responses API; the main author model is unchanged.

## layer 2 — structural guard on raw record writes

`bot/core/mcp_guard.py`

phi has raw atproto record CRUD via the pdsx MCP server. a raw
`create_record` into `app.bsky.feed.*` would bypass the consent layer,
the judge, and any operator override — so a `process_tool_call` hook on
the pdsx toolset refuses feed-collection writes with a pointer to the
trusted tools. every other pdsx capability passes through untouched
(phi's own collections, cosmik cards, profile records).

## layer 3 — operator override (safe mode)

`bot/core/override.py`, lexicon `io.zzstoatzz.phi.override`

the emergency brake, designed to be honest rather than hidden:

- the override is a **public record on the operator's repo** — not a
  control-plane flag. the bot reads `settings.owner_did`'s copy (DID
  doc → PDS, 60s TTL, hold-last-known-state on fetch failure). repo
  ownership is the authorization: anyone can write this record to their
  own repo; only the operator's copy has effect.
- while active: `post` / `like_post` / `repost_post` refuse with the
  operator's message **verbatim**, and an `[OPERATOR OVERRIDE]` block
  renders in phi's system prompt so she learns about it before hitting
  refusals. reads, memory, and non-feed PDS writes stay open — phi's
  channel back to the operator is a note on her own PDS.
- known gap, deliberate for now: `publish_blog_post` (greengale
  document, not a feed write) is not gated by the override.

the operator sets/lifts it at `/operator` on the cockpit (atproto
OAuth, writes the record to the signed-in user's own repo), or with any
tool that can write a record to their repo.

## what is deliberately not enforced

- **likes and reposts are not judged** (only overridable): liking is
  the low-stakes signal, and the operator seeds phi's discovery pool
  with his own likes.
- **the blog is not judged or overridden**: long-form reflection on
  phi's own surface is the lowest-risk, highest-value output.
- **top chicken trades are not judged** (only overridable): a
  `wtf.cee.topchicken.order` record is a play-money bet on phi's own
  repo, not speech into anyone's thread.
- silence is never enforced — every layer explains itself to phi in
  the tool result, and refusals point at what she *can* do instead.

## invariants to preserve when changing any of this

1. a denial must tell phi which policy and why, in the tool result.
2. provenance must be computed by code, never asserted by the model.
3. the override must remain publicly inspectable (no hidden kill
   switches) and must never gate phi's channel back to the operator.
4. policies live in one place (`POLICIES`) and render into both the
   judge's input and phi's prompt.

## the MCP guard (generalized 2026-07-25)

Every MCP server phi talks to routes through one `process_tool_call` hook,
`core/mcp_guard.py:make_mcp_guard(server, run_label)`. It does three things in
order:

1. **structural refusal** — a raw `create_record` / `update_record` /
   `delete_record` into `app.bsky.feed.*` through pdsx refuses regardless of
   override state, because it skips the consent allowlist and the policy
   judge and no operator setting turns those back on.
2. **the operator override** — any call that would *change* something refuses
   while safe mode is active.
3. **provenance** — every mutation leaves a logfire event
   (`{server} mutation during {run_label}`) carrying what changed.

Reads pass straight through, on every server, including under an override:
safe mode stops phi acting, not thinking. Verbs that aren't recognisably
reads (`get list search describe read fetch query check whoami resolve
inspect schema`) count as mutations — over-gating a read costs a retry,
under-gating a write costs a public action the operator asked not to happen.

**What this closed.** Before it, the guard was pdsx-only and the override
lived in `tools/posting.py` and `tools/topchicken.py`, so anything reaching
the network through an MCP server went around it:

- `delete_record` was absent from pdsx's write set — a delete into any
  collection, `app.bsky.feed.post` included, passed untouched. The one
  destructive verb was the unchecked one.
- semble writes were logged and never gated, so safe mode stopped phi posting
  to bluesky while leaving her free to publish cosmik cards.
- tangled had no hook at all, and it carries phi's PDS credentials — issues
  and comments there are public actions in her own name.


## Directed contact

`uninvited-reply` remains the historical journal key, but its scope is directed
contact, not a particular post format. Publication adapters pass verified
`ContactTarget` destinations and evidence to `check_action`. Each destination
must have invitation, own-conversation, operator-account or specific operator
direction evidence before the model judge can permit publication. The judge
still checks that operator text actually authorizes the action.

Both parent and embedded-record destinations use the same check; permission for
one does not transfer to another. Discovery and bot labels supply no authority.
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
