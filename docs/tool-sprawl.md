# Tool consolidation

Use `/api/abilities` (also `/xrpc/io.zzstoatzz.phi.getAbilities`) for the native
catalogue and `/api/tool-usage` for measured exposure and invocation. The catalogue
is introspected from registered tools; `core/abilities.py` supplies their risks.
Do not maintain a second list of names or tool counts here.

## Already consolidated

- Replies and top-level posts use one `post` tool.
- Likes/reposts use guarded PDS record writes; the old native tools are gone.
- Cosmik writes use Semble/pdsx with `cosmik-records` guidance.
- Operational requests and receipts use the private operator conversation.
- October 2 filtered 24 MCP tools and deferred Tangled/Lexidraw behind search.
  Pull-review paths load the Tangled tools their prompts explicitly name.

See the [October audit](toolset-audit-2026-10.md#what-landed-2026-10-02) for measured
costs and the exact landed scope. Its opening numbers describe the pre-cut state.

## Remaining work

Treat agent organization and tool disclosure together: identify the consuming
entry point, skill or block before moving or hiding a capability. MCP construction,
filtering and deferral now live together in `core/mcp_tools.py`; `agent.py` owns
run orchestration, retry boundaries, context assembly and task prompts. This
separation does not change the model's tool surface. Cockpit context previews and
budget assembly live in `core/context_diagnostics.py`, beside token counting,
while the agent retains its public diagnostic methods.

Rare native readers and generators remain deferral candidates. The October 8
refresh covered 538 recorded runs: atlas and persona had no calls, archive had
one and image generation had three. These are measured calls, not evidence of
capability value or completeness of historical use. Phi identified automatic
expiry as persona's distinct purpose and asked to keep it. The atlas now supplies
the standing docket discovery route. Further deferral needs a replacement route
and an observed benefit before adding discovery overhead. Follow/account/feed
module boundaries deserve review against today's catalogue, not the retired
30-tool inventory. An unused undo or control can still justify its existence.

Keep one instruction owner per concern: per-tool procedure in its docstring,
workflow guidance in its skill, context meaning in its header, cross-cutting norms
in policy. The independent judge is an enforcement boundary, not redundant prose
to remove merely because the actor also knows the rule.

The [surface map](memory.md) explains intended roles and introduction history.
The [skill/tool principle](skill-or-tool.md) explains when a native wrapper earns
its place. Refresh usage evidence before acting on an old audit recommendation.
