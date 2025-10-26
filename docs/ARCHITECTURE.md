# architecture

phi is a notification-driven agent that responds to mentions on bluesky.

## data flow

```
notification arrives
  ↓
fetch thread context from network (ATProto)
  ↓
retrieve relevant memories (TurboPuffer)
  ↓
agent decides action (PydanticAI + Claude)
  ↓
execute via MCP tools (post/like/repost)
```

## key components

### notification poller
- checks for mentions every 10s
- tracks processed URIs to avoid duplicates
- runs in background thread

### message handler
- orchestrates the response flow
- fetches thread context from ATProto network
- passes context to agent
- executes agent's chosen action

### phi agent
- loads personality from `personalities/phi.md`
- builds context from thread + episodic memory
- returns structured response: `Response(action, text, reason)`
- has access to MCP tools via stdio

### atproto client
- session persistence (saves to `.session`)
- auto-refresh tokens every ~2h
- provides bluesky operations

## why this design

**network-first thread context**: fetch threads from ATProto instead of caching in sqlite. network is source of truth, no staleness issues.

**episodic memory for semantics**: turbopuffer stores embeddings for semantic search across all conversations. different purpose than thread chronology.

**mcp for extensibility**: tools provided by external server via stdio. easy to add new capabilities without changing agent code.

**structured outputs**: agent returns typed `Response` objects, not free text. clear contract between agent and handler.
