from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from pydantic_ai.models.test import TestModel

from bot import agent as agent_module
from bot.agent import PhiAgent
from bot.tools._helpers import PhiDeps


async def test_private_run_reads_shared_history_without_receiving_a_memory_writer(
    monkeypatch,
):
    monkeypatch.setattr(agent_module.settings, "turbopuffer_api_key", None)
    monkeypatch.setattr(agent_module.settings, "openai_api_key", None)
    monkeypatch.setattr(agent_module.settings, "agent_model", TestModel())
    monkeypatch.setattr(agent_module.settings, "skill_mcp_urls", [])
    monkeypatch.setattr(agent_module, "CacheObservingModel", lambda _: TestModel())
    read = AsyncMock(return_value="[CHRONICLE] Previous public work.")
    monkeypatch.setattr(agent_module, "get_chronicle_block", read)
    phi = PhiAgent()
    phi.memory = Mock()
    blocks = dict(phi.context_blocks)
    deps = PhiDeps(
        author_handle="operator", memory=None, private_message_context="Private."
    )
    ctx = SimpleNamespace(deps=deps)

    assert await blocks["inject_chronicle"](ctx) == "[CHRONICLE] Previous public work."
    read.assert_awaited_once_with(phi.memory.client)
    assert deps.memory is None
