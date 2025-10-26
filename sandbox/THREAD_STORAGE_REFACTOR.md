# thread storage refactor: removing data duplication

## the problem

we're duplicating thread data that already exists on the atproto network. specifically:

```python
# database.py - thread_messages table
CREATE TABLE IF NOT EXISTS thread_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_uri TEXT NOT NULL,
    author_handle TEXT NOT NULL,
    author_did TEXT NOT NULL,
    message_text TEXT NOT NULL,
    post_uri TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

this stores messages that are already:
- living on users' personal data servers (PDSs)
- aggregated by the bluesky AppView
- accessible on-demand via `client.get_thread(uri, depth=100)`

## why this is duplicative

### the appview already does this work

when we call `get_thread()`, the appview:
1. stitches together posts from multiple PDSs
2. resolves parent/child relationships
3. returns the complete thread structure
4. handles deletions, edits, and blocks

we're then taking this data and copying it into sqlite, where it becomes:
- stale (if posts are deleted/edited)
- disconnected from the source of truth
- an unnecessary maintenance burden

### our own scripts prove this

```python
# sandbox/view_thread.py - fetches threads without local storage
def fetch_thread(post_uri: str):
    response = httpx.get(
        "https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread",
        params={"uri": post_uri, "depth": 100}
    )
    return response.json()["thread"]
```

this script demonstrates that thread data is readily available from the network. we don't need to cache it in sqlite to access it.

## what we should keep: turbopuffer

crucially, **turbopuffer is NOT duplicative**. it serves a completely different purpose:

### turbopuffer = semantic memory (essential)
- stores embeddings for semantic search
- answers: "what did we discuss about birds last week?"
- provides episodic memory across ALL conversations
- enables pattern recognition and relationship building
- core to the IIT consciousness exploration

### sqlite thread_messages = chronological cache (redundant)
- stores literal thread messages
- answers: "what was said in this specific thread?"
- duplicates data already on network
- provides no semantic search capability

the difference:
```python
# turbopuffer usage (semantic search) - KEEP THIS
memory_context = await memory.get_user_memories(
    user_handle="alice.bsky.social",
    query="birds"  # semantic search across all conversations
)

# sqlite usage (thread retrieval) - REMOVE THIS
thread_context = thread_db.get_thread_messages(thread_uri)
# ^ this is just retrieving what we could fetch from network
```

## proposed architecture

### current flow (with duplication)
```
mention received
  → fetch thread from network (get_thread)
  → store all messages in sqlite
  → read back from sqlite
  → build thread context string
  → pass to agent
```

### proposed flow (network-first)
```
mention received
  → fetch thread from network (get_thread)
  → extract messages directly
  → build thread context string
  → pass to agent
```

### with optional caching
```
mention received
  → check in-memory cache (TTL: 5 minutes)
  → if miss: fetch thread from network
  → extract messages + cache
  → build thread context string
  → pass to agent
```

## implementation plan

### phase 1: extract thread parsing logic

create a utility that converts raw atproto thread data to context:

```python
# bot/utils/thread.py (already exists, extend it)
def build_thread_context(thread_node) -> str:
    """Build conversational context from ATProto thread structure.

    Returns formatted string like:
    @alice: I love birds
    @phi: me too! what's your favorite?
    @alice: especially crows
    """
    posts = extract_posts_chronological(thread_node)

    messages = []
    for post in posts:
        handle = post.author.handle
        text = post.record.text
        messages.append(f"@{handle}: {text}")

    return "\n".join(messages)
```

### phase 2: update message handler

```python
# bot/services/message_handler.py - BEFORE
# Get thread context from database
thread_context = thread_db.get_thread_messages(thread_uri)

# bot/services/message_handler.py - AFTER
# Fetch thread from network
thread_data = await self.client.get_thread(thread_uri, depth=100)
thread_context = build_thread_context(thread_data.thread)
```

### phase 3: remove sqlite thread storage

**delete:**
- `thread_messages` table definition
- `add_message()` method
- `get_thread_messages()` method
- all calls to `thread_db.add_message()`

**keep:**
- `approval_requests` table (for future self-modification)
- database.py module structure

### phase 4: optional caching layer

if network latency becomes an issue:

```python
from functools import lru_cache
from datetime import datetime, timedelta

class ThreadCache:
    def __init__(self, ttl_seconds: int = 300):  # 5 minute TTL
        self._cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, thread_uri: str) -> str | None:
        if thread_uri in self._cache:
            context, timestamp = self._cache[thread_uri]
            if datetime.now() - timestamp < self.ttl:
                return context
        return None

    def set(self, thread_uri: str, context: str):
        self._cache[thread_uri] = (context, datetime.now())
```

## risk analysis

### risk: increased latency

**likelihood**: low
- get_thread() is fast (typically <200ms)
- we already call it for thread discovery
- public api is highly available

**mitigation**: add caching if needed

### risk: rate limiting

**likelihood**: low
- we only fetch threads when processing mentions
- mentions are relatively infrequent
- session persistence already reduces auth overhead

**mitigation**:
- implement exponential backoff
- cache frequently accessed threads

### risk: offline/network failures

**likelihood**: low
- if network is down, we can't post anyway
- existing code already handles get_thread() failures

**mitigation**:
- wrap in try/except (already doing this)
- graceful degradation (process without context)

### risk: breaking existing behavior

**likelihood**: medium
- thread discovery feature relies on storing messages
- need to ensure we don't lose context awareness

**mitigation**:
- thorough testing before/after
- evaluate thread context quality in evals

## benefits

### 1. simpler architecture
- one less database table to maintain
- no synchronization concerns
- no stale data issues

### 2. source of truth
- network data is always current
- deletions/edits reflected immediately
- no divergence between cache and reality

### 3. reduced storage
- no unbounded growth of thread_messages table
- only store what's essential (turbopuffer memories)

### 4. clearer separation of concerns
```
atproto network = thread chronology (what was said when)
turbopuffer = episodic memory (what do i remember about this person)
```

## comparison to reference projects

### void
from void_memory_system.md, void uses:
- dynamic memory blocks (persona, zeitgeist, humans, scratchpad)
- no separate thread storage table
- likely fetches context on-demand from network

### penelope (hailey's bot)
from REFERENCE_PROJECTS.md:
- custom memory system with postgresql
- stores "significant interactions"
- not clear if they cache full threads or just summaries

### marvin (slackbot)
from REFERENCE_PROJECTS.md:
- uses slack's message history API directly
- no local message storage
- demonstrates network-first approach works well

## migration path

### option 1: clean break (recommended)
1. deploy new code without thread_messages usage
2. keep table for 30 days (historical reference)
3. drop table after validation period

### option 2: gradual migration
1. write to both sqlite and read from network
2. compare outputs for consistency
3. stop writing to sqlite
4. eventually drop table

### option 3: hybrid approach
1. read from network by default
2. fall back to sqlite on network failures
3. eventually remove fallback

**recommendation**: option 1 (clean break)
- simpler code
- faster to implement
- network reliability is high enough

## success metrics

### before refactor
- thread_messages table exists
- messages stored on every mention
- context built from sqlite queries

### after refactor
- thread_messages table removed
- zero sqlite writes per mention
- context built from network fetches
- same quality responses in evals

## open questions

1. **should we cache at all?**
   - start without caching
   - add only if latency becomes measurable problem

2. **what about the discovery feature?**
   - currently stores full thread when tagged in
   - can just fetch on-demand instead
   - no need to persist

3. **do we need conversation summaries?**
   - not for thread context (fetch from network)
   - maybe for turbopuffer (semantic memory)
   - separate concern from this refactor

## conclusion

removing sqlite thread storage:
- eliminates data duplication
- simplifies architecture
- maintains all essential capabilities
- aligns with atproto's "data on the web" philosophy

turbopuffer stays because it provides semantic memory - a fundamentally different capability than chronological thread reconstruction.

the network is the source of truth. we should read from it.
