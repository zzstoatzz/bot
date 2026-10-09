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
entry point, skill or block before moving or hiding a capability. `agent.py`
currently owns setup, context assembly and task prompts; moving functions alone
will not remove duplicated instructions or reduce the model's tool surface.

Rare native readers and generators remain deferral candidates. Persona predates
live personality authorship and needs a purpose decision. Follow/account/feed
module boundaries deserve review against today's catalogue, not the retired
30-tool inventory. An unused undo or control can still justify its existence.

Keep one instruction owner per concern: per-tool procedure in its docstring,
workflow guidance in its skill, context meaning in its header, cross-cutting norms
in policy. The independent judge is an enforcement boundary, not redundant prose
to remove merely because the actor also knows the rule.

The [surface map](memory.md) explains intended roles and introduction history.
The [skill/tool principle](skill-or-tool.md) explains when a native wrapper earns
its place. Refresh usage evidence before acting on an old audit recommendation.
