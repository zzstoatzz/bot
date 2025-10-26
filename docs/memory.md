# memory

phi has two distinct memory systems with different purposes.

## thread context (chronological)

**source**: ATProto network
**access**: `client.get_thread(uri, depth=100)`
**purpose**: what was said in this specific thread

fetched on-demand from the network when processing mentions. provides chronological conversation flow.

```python
# example thread context
@alice: I love birds
@phi: me too! what's your favorite?
@alice: especially crows
```

**why not cache this?**
- data already exists on network
- appview aggregates posts from PDSs
- fetching is fast (~200ms)
- network is always current (handles edits/deletions)

## episodic memory (semantic)

**source**: TurboPuffer
**access**: `memory.get_user_memories(handle, query="birds")`
**purpose**: what do i remember about this person across all conversations

uses vector embeddings (OpenAI text-embedding-3-small) for semantic search.

```python
# example episodic memories
- "alice mentioned she loves birds"
- "discussed crow intelligence with alice"
- "alice prefers corvids over other species"
```

**why vector storage?**
- semantic similarity (can't do with chronological data)
- cross-conversation patterns
- contextual retrieval based on current topic
- enables relationship building over time

## namespaces

```
phi-users-{handle}  - per-user conversation history
```

each user gets their own namespace for isolated memory retrieval.

## key distinction

| | thread context | episodic memory |
|---|---|---|
| **what** | messages in current thread | patterns across all conversations |
| **when** | this conversation | all time |
| **how** | chronological order | semantic similarity |
| **storage** | network (ATProto) | vector DB (TurboPuffer) |
| **query** | by thread URI | by semantic search |

## in practice

when processing a mention from `@alice`:

1. fetch current thread: "what was said in THIS conversation?"
2. search episodic memory: "what do i know about alice from PAST conversations?"
3. combine both into context for agent

this gives phi both immediate conversational awareness and long-term relationship memory.
