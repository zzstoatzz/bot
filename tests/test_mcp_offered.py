"""Which MCP tools phi carries (docs/toolset-audit-2026-10.md)."""

from typing import Any, cast

import pytest
from pydantic_ai.tools import ToolDefinition

from bot import agent as agent_module
from bot.agent import MCP_DROPPED, MCP_KEPT, PhiAgent, _mcp_origin, _mcp_url


def _offers(toolset, name: str) -> bool:
    filter_func = getattr(toolset, "filter_func", None)
    return filter_func is None or filter_func(
        cast(Any, None), ToolDefinition(name=name)
    )


@pytest.fixture(autouse=True)
def prefect_configured(monkeypatch):
    monkeypatch.setattr(agent_module.settings, "prefect_api_auth_string", "test")


def _by_origin() -> dict[str, Any]:
    phi = PhiAgent.__new__(PhiAgent)
    return {_mcp_origin(ts): ts for ts in phi._mcp_toolsets()}


def test_allowlisted_servers_offer_only_what_phi_uses():
    servers = _by_origin()
    assert _offers(servers["prefect"], "prefect_get_flow_runs")
    assert not _offers(servers["prefect"], "prefect_docs_search_prefect")
    assert not _offers(servers["prefect"], "prefect_a_tool_added_upstream")
    assert _offers(servers["pub"], "pub_get_document")
    assert not _offers(servers["pub"], "pub_find_similar")


def test_denylisted_servers_lose_only_the_named_tools():
    servers = _by_origin()
    assert not _offers(servers["tangled"], "tangled_delete_issue")
    assert _offers(servers["tangled"], "tangled_read_file")
    assert not _offers(servers["pdsx-by-zzstoatzz"], "whoami")
    assert _offers(servers["pdsx-by-zzstoatzz"], "create_record")


def test_tools_named_in_a_prompt_or_skill_stay_offered():
    """own-source and the pull-review prompt send phi to these by name."""
    tangled = _by_origin()["tangled"]
    for name in ("tangled_commit_log", "tangled_compare", "tangled_update_pull"):
        assert _offers(tangled, name)


def test_a_filtered_server_keeps_its_url_and_origin():
    servers = _by_origin()
    assert _mcp_url(servers["tangled"]) is not None
    assert set(MCP_KEPT) | set(MCP_DROPPED) == {
        "prefect",
        "pub-search",
        "pdsx",
        "tangled",
    }
