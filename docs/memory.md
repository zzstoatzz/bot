# memory

phi has two memory systems with different visibility and purpose.

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

## private memory (semantic)

**source**: TurboPuffer
**purpose**: what phi remembers about people across all conversations

uses vector embeddings (OpenAI text-embedding-3-small) for semantic search.

### namespaces

- **phi-core** — identity and guidelines
- **phi-users-{handle}** — per-user observations, interactions, and relationship summaries
- **phi-episodic** — phi's own notes about the world

each user gets their own namespace for isolated memory retrieval. observations accumulate over conversations; a separate pipeline periodically compacts them into relationship summaries.

## public memory (network)

**source**: cosmik records on phi's PDS, indexed by semble
**purpose**: knowledge worth preserving publicly — links, notes, connections between ideas

phi writes public records via the cosmik lexicon:
- `network.cosmik.card` (NOTE type) — text notes
- `network.cosmik.card` (URL type) — bookmarks
- `network.cosmik.connection` — semantic links between entities

these are automatically indexed by [semble](https://semble.so) and searchable by anyone on the network. phi can also search the network for cards other people have saved.

### dual-write

notes and bookmarks are written to both systems: TurboPuffer for fast private recall, PDS for public discovery. this means phi can find its own notes via either system, and other agents/people can find them via semble.

## in practice

when processing a mention from `@alice`:

1. fetch current thread: "what was said in THIS conversation?"
2. search private memory: "what do i know about alice from PAST conversations?"
3. combine both into context for agent

when phi encounters something worth preserving:

4. write to private memory (tpuf) for fast recall
5. write to public record (PDS/cosmik) for network discovery

## key distinction

| | thread context | private memory | public memory |
|---|---|---|---|
| **what** | messages in current thread | patterns across conversations | knowledge worth sharing |
| **when** | this conversation | all time | all time |
| **how** | chronological | semantic similarity | semantic search (semble) |
| **storage** | network (ATProto) | vector DB (TurboPuffer) | PDS (cosmik) + semble index |
| **visibility** | public (it's posts) | private to phi | public to everyone |
