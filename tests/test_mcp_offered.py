"""Which MCP tools phi carries (docs/toolset-audit-2026-10.md)."""

from typing import Any, cast
from unittest.mock import patch

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import DeferredLoadingToolset, FunctionToolset

from bot import agent as agent_module
from bot.agent import MCP_DROPPED, MCP_KEPT, PhiAgent, _mcp_origin, _mcp_url
from bot.tools._helpers import PhiDeps


def _offers(toolset, name: str) -> bool:
    while toolset is not None:
        filter_func = getattr(toolset, "filter_func", None)
        if filter_func is not None:
            return filter_func(cast(Any, None), ToolDefinition(name=name))
        toolset = getattr(toolset, "wrapped", None)
    return True


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


def _is_deferred(toolset) -> bool:
    while toolset is not None:
        if isinstance(toolset, DeferredLoadingToolset):
            return True
        toolset = getattr(toolset, "wrapped", None)
    return False


def _servers_for(run_label: str) -> dict[str, Any]:
    phi = PhiAgent.__new__(PhiAgent)
    return {_mcp_origin(ts): ts for ts in phi._mcp_toolsets(run_label=run_label)}


def test_tangled_is_deferred_except_where_the_prompt_names_its_tools():
    assert _is_deferred(_servers_for("batch processing")["tangled"])
    assert not _is_deferred(_servers_for("pull request review")["tangled"])
    assert not _is_deferred(_servers_for("pull request comment")["tangled"])
    assert not _is_deferred(_servers_for("batch processing")["pub"])


def test_a_deferred_server_is_still_filtered_and_still_has_its_url():
    tangled = _servers_for("batch processing")["tangled"]
    assert _mcp_url(tangled) is not None
    assert not _offers(tangled, "tangled_delete_issue")


async def test_deferred_tools_reach_the_model_only_after_a_search():
    """What a run sends: the search tool first, a found tool from the next request."""
    hidden = FunctionToolset()

    @hidden.tool_plain
    def tangled_read_file(path: str) -> str:
        """read one file"""
        return f"read {path}"

    offered: list[list[str]] = []

    def model(_messages, info: AgentInfo) -> ModelResponse:
        offered.append([tool.name for tool in info.function_tools])
        if len(offered) == 1:
            return ModelResponse(
                parts=[ToolCallPart("search_tools", {"keywords": "tangled_read_file"})]
            )
        if len(offered) == 2:
            return ModelResponse(
                parts=[ToolCallPart("tangled_read_file", {"path": "a"})]
            )
        return ModelResponse(parts=[TextPart("done")])

    phi = PhiAgent.__new__(PhiAgent)
    phi.agent = Agent(FunctionModel(model), deps_type=PhiDeps)
    with patch.object(
        PhiAgent, "_mcp_toolsets", side_effect=lambda **_: [hidden.defer_loading()]
    ):
        out = await phi._run_agent(
            label="batch processing", prompt="hi", deps=PhiDeps(author_handle="")
        )

    assert out == "done"
    # the search tool goes away once nothing is left to find
    assert offered == [["search_tools"], ["tangled_read_file"], ["tangled_read_file"]]


async def test_the_context_budget_counts_what_is_sent(monkeypatch):
    hidden = FunctionToolset()

    @hidden.tool_plain
    def tangled_read_file(path: str) -> str:
        """read one file"""
        return path

    phi = PhiAgent.__new__(PhiAgent)
    phi.memory = None
    phi.agent = Agent(model=TestModel())
    monkeypatch.setattr(phi, "skills_toolset", FunctionToolset(), raising=False)
    monkeypatch.setattr(
        phi, "_mcp_toolsets", lambda run_label="": [hidden.defer_loading()]
    )

    assert [tool.name for _, tool in await phi.list_tool_definitions()] == [
        "search_tools"
    ]
