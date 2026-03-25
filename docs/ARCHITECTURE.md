# architecture

phi is a notification-driven agent that responds to activity on bluesky.

## data flow

```
notification arrives (mention, reply, quote, like, repost, follow)
  ↓
fetch thread context from network (ATProto)
  ↓
retrieve relevant memories (TurboPuffer)
  ↓
agent decides action (PydanticAI + Claude)
  ↓
execute action + store observations
```

## key components

### notification poller
- checks for all notification types every 10s
- tracks processed URIs to avoid duplicates
- triggers daily reflection at a configured hour

### message handler
- orchestrates the response flow
- fetches thread context from ATProto network
- passes context to agent
- executes agent's chosen action

### phi agent
- loads personality from `personalities/phi.md`
- builds context from thread + private memory + network knowledge
- returns structured response: `Response(action, text, reason)`
- native tools defined in `agent.py`, MCP tools from remote servers

### atproto client
- session persistence (saves to `.session`)
- auto-refresh tokens every ~2h
- provides bluesky operations

## why this design

**network-first thread context**: fetch threads from ATProto instead of caching locally. network is source of truth, no staleness issues.

**private + public memory**: turbopuffer stores private embeddings for semantic recall across conversations. cosmik records on PDS provide public knowledge that's indexed by semble for network-wide discovery. dual-write means phi gets both fast private recall and public visibility.

**mcp for extensibility**: tools provided by remote MCP servers (pdsx for atproto CRUD, pub-search for publications). easy to add new capabilities without changing agent code.

**structured outputs**: agent returns typed `Response` objects, not free text. clear contract between agent and handler.
