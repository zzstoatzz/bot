# mcp integration

phi uses the [model context protocol](https://modelcontextprotocol.io) to access external tools hosted as remote servers.

## servers

phi connects to two MCP servers via `MCPServerStreamableHTTP` (pydantic-ai):

- **[pdsx](https://pdsx-by-zzstoatzz.fastmcp.app)** — atproto record CRUD. authenticated with phi's bluesky credentials. used for reading/writing posts, profiles, and records on any PDS.
- **[pub-search](https://pub-search-by-zzstoatzz.fastmcp.app)** — publication search across leaflet, whitewind, and other long-form writing platforms. prefixed as `pub_*` to avoid tool name collisions.

## why mcp

- **separation**: tools live in external servers, not in phi's codebase
- **extensibility**: add new capabilities by connecting another server
- **reusability**: same servers can be used by other agents or tools
- **no local dependencies**: phi doesn't need to bundle atproto client libraries for record CRUD

## how it works

MCP servers are created fresh per `agent.run()` call to avoid connection scope issues. the agent enters each server's async context before running, so parallel tool calls share the connection.

```python
toolsets = self._mcp_toolsets()
async with contextlib.AsyncExitStack() as stack:
    for ts in toolsets:
        await stack.enter_async_context(ts)
    result = await self.agent.run(prompt, deps=deps, toolsets=toolsets)
```

## native tools vs MCP tools

phi has two kinds of tools:

- **native tools** (defined in `agent.py`) — memory, search, cosmik records, trending, URL checks. these need direct access to phi's deps (memory client, config, etc).
- **MCP tools** (from remote servers) — atproto CRUD, publication search. these are stateless HTTP calls that don't need phi's internal state.

the agent sees all tools uniformly and picks the right one for the task.
