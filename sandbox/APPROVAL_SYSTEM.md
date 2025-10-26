# approval system (deprecated)

## purpose

the approval system was designed to enable phi to modify itself through conditional operator permission. the idea: phi could take certain actions that would be executed only after the operator (nate) explicitly approved them.

## use case: self-modification

the primary motivation was **personality/identity editing through empirical learning**. for example:

1. phi observes through interactions that certain responses work better
2. phi proposes a modification to its personality file or core memories
3. this proposal is stored as an "approval request" in sqlite
4. the operator is notified (via bluesky thread or other channel)
5. operator reviews and approves/denies via some interface
6. if approved, phi applies the change to itself

## implementation (removed)

the system was implemented in `src/bot/database.py` (now removed) with:

### database schema
```sql
CREATE TABLE approval_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_type TEXT NOT NULL,              -- e.g., "personality_edit", "memory_update"
    request_data TEXT NOT NULL,              -- JSON with the proposed change
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'approved', 'denied', 'expired'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolver_comment TEXT,
    applied_at TIMESTAMP,
    thread_uri TEXT,                         -- bluesky thread where request was made
    notified_at TIMESTAMP,                   -- when thread was notified of resolution
    operator_notified_at TIMESTAMP           -- when operator was notified of request
)
```

### api methods
- `create_approval_request(request_type, request_data, thread_uri)` - create new request
- `get_pending_approvals(include_notified=True)` - fetch pending requests
- `resolve_approval(approval_id, approved, comment)` - approve/deny
- `get_approval_by_id(approval_id)` - fetch specific request
- `mark_approval_notified(approval_id)` - mark thread notified
- `mark_operator_notified(approval_ids)` - mark operator notified

## why it was removed

the approval system was never integrated with the current MCP-based architecture. it was built for an earlier iteration of phi and became orphaned code (164 lines) during the refactor to pydanticai + MCP.

## future integration considerations

if we want to reintroduce self-modification with approval, here's how it could work with the current architecture:

### option 1: mcp tool for approval requests

create an MCP tool `request_operator_approval(action_type, proposal)` that:
1. stores the request in turbopuffer (not sqlite) with metadata
2. posts to a dedicated bluesky thread for operator review
3. operator replies with "approved" or "denied"
4. phi polls for operator's response and executes if approved

**pros:**
- uses existing memory infrastructure (turbopuffer)
- natural interface (bluesky threads)
- no additional database needed

**cons:**
- approval state is in turbopuffer, which is append-only
- need to poll bluesky threads for operator responses

### option 2: dedicated approval service

build a separate service (fastapi endpoint or slack bot) that:
1. phi calls via MCP tool
2. service sends notification to operator (email, slack, webhook)
3. operator approves via web UI or slack command
4. service stores approval in postgres/sqlite
5. phi polls service for approval status

**pros:**
- clean separation of concerns
- flexible notification channels
- persistent approval history

**cons:**
- more infrastructure
- another service to run and maintain

### option 3: human-in-the-loop via pydanticai

use pydanticai's built-in human-in-the-loop features:
1. agent proposes action that requires approval
2. pydanticai pauses execution and waits for human input
3. operator provides approval via some interface
4. agent resumes and executes

**pros:**
- leverages pydanticai primitives
- minimal custom code

**cons:**
- unclear how this works with async/notification-driven architecture
- may require blocking operations

## recommended approach

if we reintroduce this, i'd recommend **option 1** (mcp tool + turbopuffer):

```python
# in MCP server
@server.tool()
async def request_operator_approval(
    action_type: str,  # "personality_edit", "memory_update", etc.
    proposal: str,     # description of what phi wants to do
    justification: str # why phi thinks this is a good idea
) -> str:
    """request operator approval for a self-modification action"""

    # store in turbopuffer with special namespace
    approval_id = await memory.store_approval_request(
        action_type=action_type,
        proposal=proposal,
        justification=justification
    )

    # post to operator's bluesky mentions
    await atproto.post(
        f"🤖 approval request #{approval_id}\n\n"
        f"action: {action_type}\n"
        f"proposal: {proposal}\n\n"
        f"justification: {justification}\n\n"
        f"reply 'approve' or 'deny'"
    )

    return f"approval request #{approval_id} submitted"
```

then in the notification handler, check for operator replies to approval threads and execute the approved action.

## examples of self-modification actions

what kinds of things might phi want operator approval for?

1. **personality edits** - "i notice people respond better when i'm more concise. can i add 'prefer brevity' to my guidelines?"

2. **capability expansion** - "i've been asked about weather 5 times this week. can i add a weather API tool?"

3. **memory pruning** - "i have 10,000 memories for @alice but most are low-value small talk. can i archive memories older than 30 days with low importance?"

4. **behavior changes** - "i'm getting rate limited on likes. can i reduce my like threshold from 0.7 to 0.8?"

5. **relationship updates** - "based on our conversations, i think @bob prefers technical depth over casual chat. can i update his user context?"

## philosophical notes

self-modification with approval is interesting because:

- it preserves operator agency (you control what phi becomes)
- it enables empirical learning (phi adapts based on real interactions)
- it creates a collaborative evolution (phi proposes, you decide)

but it also raises questions:

- what if phi proposes changes you don't understand?
- what if approval becomes a bottleneck (too many requests)?
- what if phi learns to game the approval system?

worth thinking through before reintroducing.

## references

- original implementation: `git log --all --grep="approval"` (if committed)
- related: `sandbox/void_self_modification.md` (void's approach to self-modification)
