# mcp integration

phi uses the [model context protocol](https://modelcontextprotocol.io) to access external tools hosted as remote servers, connected via `MCPServerStreamableHTTP` (pydantic-ai). the authoritative list is `_mcp_toolsets` in `src/bot/agent.py`; currently: pdsx (atproto record CRUD, phi's credentials), pub-search (long-form publication search), semble (ranked search + call surface over phi's public knowledge graph), tangled (code collab — repos, issues, PRs), and prefect (workflow state, only when auth is configured).

## why mcp

- **separation**: tools live in external servers, not in phi's codebase
- **extensibility**: add new capabilities by connecting another server
- **reusability**: same servers can be used by other agents or tools
- **no local dependencies**: phi doesn't need to bundle client libraries for each surface

## how it works

MCP servers are created fresh per `agent.run()` call to avoid connection scope issues. the agent enters each server's async context before running, so parallel tool calls share the connection.

```python
toolsets = self._mcp_toolsets(run_label=label)
async with contextlib.AsyncExitStack() as stack:
    for ts in toolsets:
        await stack.enter_async_context(ts)
    result = await self.agent.run(prompt, deps=deps, toolsets=toolsets)
```

## process_tool_call hooks

surfaces are not permission boundaries — a server that accepts phi's credentials will do whatever the credentials allow. where the boundary matters, it lives in a `process_tool_call` hook on the toolset (`src/bot/core/mcp_guard.py`):

- **pdsx**: structural guard. raw `app.bsky.feed.*` writes refuse with a pointer to the trusted posting tools, so the consent layer / policy judge / operator override can't be bypassed (see `docs/safety.md`).
- **semble**: observational logger. every library write leaves a logfire event with the run label and the sdk method called, so card provenance is queryable. safe mode refuses the write.

## notes on semble

semble's hosted server exposes the whole sdk (51 methods) behind two meta-tools: `search_tools` ranks the methods against a plain-language request with TypeSafe's jev model and returns the best fits with schemas; `call_tool` runs one by name. that is jev mode (since 2026-09-19). before it the server ran code mode (`search` / `get_schema` / `execute`, a python sandbox composing sdk calls); the operator can switch the hosted instance back with one command, and the guard still understands both surfaces. either way it is the anti-sprawl move (`docs/tool-sprawl.md`). facts worth keeping:

- **appview writes are protocol-native.** writes through the semble api land as real `network.cosmik.*` records on the repo of the account behind the api key, and deletes propagate to the pds. verified experimentally 2026-06-11 (write via api → read the record straight off the pds → delete via api → gone from the pds).
- **a call with a key carries the key's full read/write power.** the consent story for semble writes is norms + the write logger + the operator override, not a structural gate; writes there are public and attributed to phi. the guard reads the sdk method out of `call_tool`'s arguments (or out of the submitted code in code mode) to decide whether a call mutates; unknown methods count as writes.
- **jev mode returns every record into context.** one sdk call per turn, no sandbox to aggregate in. tasks that page across many records (six libraries, ~1,200 cards) are the known gap; pages cap at 100.

## native tools vs MCP tools

phi has two kinds of tools:

- **native tools** (defined in `src/bot/tools/`) — memory, search, trending, feeds, posting. these need direct access to phi's deps (memory client, config, etc).
- **MCP tools** (from remote servers) — stateless HTTP calls that don't need phi's internal state.

the agent sees all tools uniformly and picks the right one for the task.

The native `read_web_page` tool retains each complete web extraction in the
current run's `PhiDeps.web_sources`. Returned slices identify the capture with
`source_id`, `captured_at`, and a SHA-256 of the full extracted text. Continuing
with that ID reads the same extraction without another network request; omitting
it fetches fresh content. Unknown IDs and mismatched URLs fail explicitly.
Captures are immutable, last only for the run, and are not public archive links.
Bluesky URLs still use the native record and image reader. A capture hash proves
which extracted text was read, not that extraction reproduced the entire page.
