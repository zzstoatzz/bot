"""The guard must call through pydantic-ai's real MCP dispatch, not a stub.

2026-11-01: after the move to pydantic-ai 2 the guard passed `metadata`
positionally to `call_tool`, which v2 made keyword-only. Every MCP tool call
raised TypeError for every server, and the tests stubbed `call_tool`, so
none of them noticed.
"""

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic_ai import RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from bot.core.mcp_guard import make_mcp_guard
from bot.tools._helpers import PhiDeps


def _ctx() -> RunContext[PhiDeps]:
    return RunContext[PhiDeps](
        deps=PhiDeps(author_handle=""), model=TestModel(), usage=RunUsage()
    )


async def _call(server: FastMCP, name: str, args: dict) -> str:
    toolset = MCPToolset(server, process_tool_call=make_mcp_guard("pdsx", "test run"))
    async with toolset:
        tools = await toolset.get_tools(_ctx())
        return str(await toolset.call_tool(name, args, _ctx(), tools[name]))


async def test_a_guarded_read_reaches_the_server():
    server = FastMCP("docs")

    @server.tool
    def search_atproto_docs(query: str) -> str:
        return f"found {query}"

    assert "found rev" in await _call(server, "search_atproto_docs", {"query": "rev"})


# 2026-11-02: tool-call markup leaked into `repo`, pdsx answered "URL too
# long", and the guard called that an outage, so phi dropped half her answer.
# An error the server returns is a fact about the arguments.


async def test_an_error_the_server_returns_is_not_an_outage():
    server = FastMCP("pdsx")

    @server.tool
    def list_records(repo: str) -> str:
        raise ToolError("URL too long")

    result = await _call(server, "list_records", {"repo": '">did:plc:x</parameter'})
    assert "URL too long" in result
    assert "unavailable" not in result
    assert "check the arguments" in result


async def test_a_missing_repo_says_to_resolve_the_did():
    server = FastMCP("pdsx")

    @server.tool
    def get_record(repo: str) -> str:
        raise ToolError("RepoNotFound: Could not find repo")

    result = await _call(server, "get_record", {"repo": "nobody.test"})
    assert "resolve its DID" in result


async def test_a_transport_failure_is_an_outage():
    async def unreachable(name, args, *, metadata=None):
        raise httpx.ConnectError("Connection refused")

    guard = make_mcp_guard("semble", "test run")
    result = await guard(None, unreachable, "search", {})
    assert "unavailable right now" in result
    assert "skip that call" in result


async def test_rejected_read_reaches_server_again_only_with_corrected_arguments():
    server = FastMCP("pdsx")
    calls = []

    @server.tool
    def list_records(repo: str) -> str:
        calls.append(repo)
        if repo == "malformed":
            raise ToolError("URL too long")
        return "records found"

    toolset = MCPToolset(server, process_tool_call=make_mcp_guard("pdsx", "test run"))
    ctx = _ctx()
    async with toolset:
        tool = (await toolset.get_tools(ctx))["list_records"]
        first = await toolset.call_tool(
            "list_records", {"repo": "malformed"}, ctx, tool
        )
        repeat = await toolset.call_tool(
            "list_records", {"repo": "malformed"}, ctx, tool
        )
        fixed = await toolset.call_tool("list_records", {"repo": "phi.test"}, ctx, tool)

    assert "URL too long" in str(first)
    assert "No request sent" in str(repeat)
    assert "records found" in str(fixed)
    assert calls == ["malformed", "phi.test"]


async def test_unsupported_pdsx_decoder_points_to_raw_records():
    server = FastMCP("pdsx")

    @server.tool
    def list_records(collection: str) -> str:
        raise ToolError(
            "module 'atproto_client.models.social.grain.gallery' has no attribute 'Record'"
        )

    result = await _call(server, "list_records", {"collection": "social.grain.gallery"})
    assert "com.atproto.repo.listRecords" in result
    assert "cannot decode this collection" in result


async def test_local_dispatch_bug_does_not_imply_outage():
    async def broken_dispatch(name, args):
        raise TypeError("unexpected positional argument")

    result = await make_mcp_guard("pdsx")(None, broken_dispatch, "get_record", {})
    assert "failed during dispatch (TypeError)" in result
    assert "unavailable" not in result
