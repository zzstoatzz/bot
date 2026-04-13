# architecture

phi is a notification-driven agent on bluesky. it also posts original thoughts on a schedule and explores interesting accounts when idle.

## data flow

```
notification batch arrives (all types)
  ↓
fetch thread context + stranger lookups
  ↓
inject memories (per-user, episodic, public)
  ↓
agent decides + acts via tool calls (reply, like, post, note, etc)
  ↓
extract observations for next time
```

## scheduling

- **notifications**: polled every 10s, dispatched as one cognitive event per batch
- **thought posts**: every 2h during configured hours — reads timeline, trending, feeds
- **daily reflection**: once per day — reviews recent activity, posts synthesis
- **exploration**: event-driven — drains curiosity queue when system is idle (no cron)

## why this design

**tool-based actions**: phi decides AND acts inside one agent run via tool calls. no separate action dispatch layer.

**network-first context**: threads fetched from ATProto on demand. network is source of truth.

**private + public memory**: turbopuffer for private semantic recall. cosmik/semble for public knowledge discovery.

**mcp for extensibility**: atproto CRUD and publication search via remote MCP servers.
