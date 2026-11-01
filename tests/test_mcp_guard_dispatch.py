"""The guard must call through pydantic-ai's real MCP dispatch, not a stub.

2026-11-01: after the move to pydantic-ai 2 the guard passed `metadata`
positionally to `call_tool`, which v2 made keyword-only. Every MCP tool call
raised TypeError for every server, and the tests stubbed `call_tool`, so
none of them noticed.
"""

from fastmcp import FastMCP
from pydantic_ai import RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from bot.core.mcp_guard import make_mcp_guard
from bot.tools._helpers import PhiDeps


async def test_a_guarded_read_reaches_the_server():
    server = FastMCP("docs")

    @server.tool
    def search_atproto_docs(query: str) -> str:
        return f"found {query}"

    toolset = MCPToolset(
        server, process_tool_call=make_mcp_guard("atproto-docs", "test run")
    )
    ctx = RunContext[PhiDeps](
        deps=PhiDeps(author_handle=""), model=TestModel(), usage=RunUsage()
    )
    async with toolset:
        tools = await toolset.get_tools(ctx)
        result = await toolset.call_tool(
            "search_atproto_docs", {"query": "rev"}, ctx, tools["search_atproto_docs"]
        )
    assert "found rev" in str(result)
