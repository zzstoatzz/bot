"""A private operator conversation reads her memory and writes none of it."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from bot import agent as agent_module
from bot.agent import PhiAgent
from bot.core.operator_reports import conversation_material
from bot.tools._helpers import PhiDeps
from bot.tools.memory import register

OPERATOR = "did:plc:operator"
HISTORY = [
    {"id": "1", "author": "did:plc:phi", "sent": 1, "text": "Tunnel is back."},
    {"id": "2", "author": OPERATOR, "sent": 2, "text": "i meant the float records"},
]


@pytest.fixture
def private_run(monkeypatch):
    monkeypatch.setattr(agent_module.settings, "turbopuffer_api_key", None)
    monkeypatch.setattr(agent_module.settings, "openai_api_key", None)
    monkeypatch.setattr(agent_module.settings, "agent_model", TestModel())
    monkeypatch.setattr(agent_module.settings, "skill_mcp_urls", [])
    monkeypatch.setattr(agent_module.settings, "owner_did", OPERATOR)
    monkeypatch.setattr(agent_module, "CacheObservingModel", lambda _: TestModel())
    monkeypatch.setattr(agent_module, "list_goal_records", AsyncMock(return_value=[]))
    phi = PhiAgent()
    memory = Mock()
    memory.get_episodic_context = AsyncMock(return_value="[RELEVANT MEMORIES]")
    memory.build_user_context = AsyncMock(return_value="[ABOUT]")
    memory.store_episodic_memory = AsyncMock()
    phi.memory = memory
    deps = PhiDeps(
        author_handle="operator",
        memory=memory,
        private_message_context=conversation_material(HISTORY, ["2"]),
    )
    return dict(phi.context_blocks), SimpleNamespace(deps=deps), memory


async def test_recall_is_cued_by_the_operators_new_messages(private_run):
    blocks, ctx, memory = private_run

    assert await blocks["inject_episodic"](ctx) == "[RELEVANT MEMORIES]"
    assert memory.get_episodic_context.await_args.args == ("i meant the float records",)

    assert "[ABOUT]" in await blocks["inject_user_memory"](ctx)
    recalled = {
        call.args[0]: call.kwargs["query_text"]
        for call in memory.build_user_context.await_args_list
    }
    assert recalled == dict.fromkeys(
        agent_module.settings.operator_handles, "i meant the float records"
    )


async def test_chronicle_renders_and_the_discovery_pool_does_not(
    private_run, monkeypatch
):
    blocks, ctx, memory = private_run
    read = AsyncMock(return_value="[CHRONICLE] Previous public work.")
    monkeypatch.setattr(agent_module, "get_chronicle_block", read)
    pool = AsyncMock(return_value="[DISCOVERY POOL]")
    monkeypatch.setattr(agent_module, "get_discovery_pool_block", pool)

    assert await blocks["inject_chronicle"](ctx) == "[CHRONICLE] Previous public work."
    assert await blocks["inject_discovery_pool"](ctx) == ""
    pool.assert_not_awaited()


async def test_save_memory_declines_and_says_memory_is_working(private_run):
    _, ctx, memory = private_run
    agent = Agent()
    register(agent)
    save = agent._function_toolset.tools["save_memory"].function

    result = await save(
        RunContext(deps=ctx.deps, model=TestModel(), usage=RunUsage()),
        "the operator meant the float request literally",
        ["operator"],
    )

    assert result.startswith("Not saved.")
    assert "nothing is down" in result
    memory.store_episodic_memory.assert_not_awaited()
