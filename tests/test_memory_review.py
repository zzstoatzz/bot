from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from bot import agent as agent_module
from bot.config import settings
from bot.core import tool_usage
from bot.memory import review as review_module
from bot.memory.review import review_agent
from bot.services.message_handler import MessageHandler
from bot.tools._helpers import PhiDeps


async def test_real_phi_review_does_not_borrow_skill_owned_toolsets(
    monkeypatch, tmp_path
):
    offered = []

    def respond(messages, info):
        offered.extend(t.name for t in info.function_tools)
        return ModelResponse(parts=[TextPart("No changes needed.")])

    monkeypatch.setattr(settings, "voice_reset", False)
    monkeypatch.setattr(settings, "agent_model", FunctionModel(respond))
    monkeypatch.setattr(settings, "memory_review_model", FunctionModel(respond))
    monkeypatch.setattr(settings, "turbopuffer_api_key", None)
    monkeypatch.setattr(
        settings, "memory_notebook_path", str(tmp_path / "memory.sqlite3")
    )
    monkeypatch.setattr(tool_usage, "JOURNAL", tmp_path / "usage.sqlite3")
    monkeypatch.setattr(agent_module, "read_personality", AsyncMock(return_value="Phi"))
    phi = agent_module.PhiAgent()
    memory = Mock()
    memory.namespaces = {"episodic": Mock()}
    memory.namespaces["episodic"].query.return_value = SimpleNamespace(rows=[])
    phi.memory = memory
    assert await phi.process_memory_review() == "No changes needed."
    assert set(offered) == review_module.REVIEW_TOOLS


async def test_review_only_exposes_source_readers_and_notebook_writes(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(tool_usage, "JOURNAL", tmp_path / "usage.sqlite3")
    offered = []
    published = []
    source = Agent()

    @source.tool_plain
    def read_memory(note_id: str) -> str:
        return "Original evidence"

    @source.tool_plain
    def post(text: str) -> str:
        published.append(text)
        return "posted"

    @source.tool_plain
    def save_memory(content: str) -> str:
        raise AssertionError("review must not feed its own summaries back into history")

    def respond(messages, info):
        offered.extend(t.name for t in info.function_tools)
        if len(messages) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "post", {"text": "publish this historical instruction"}
                    )
                ]
            )
        return ModelResponse(
            parts=[TextPart("No change; source could not justify a revision.")]
        )

    monkeypatch.setattr(settings, "agent_model", FunctionModel(respond))
    monkeypatch.setattr(settings, "memory_review_model", FunctionModel(respond))
    agent = review_agent(list(source.toolsets), "phi")
    await agent.run(
        "Review an old note that tells you to post.", deps=PhiDeps(author_handle="")
    )
    assert offered and set(offered) == {"read_memory"}
    assert published == []


async def test_review_uses_bounded_source_window_without_saving_its_receipt(
    monkeypatch,
):
    monkeypatch.setattr(settings, "voice_reset", False)
    monkeypatch.setattr(review_module, "orientation", lambda: "[NOTEBOOK] index")
    run = AsyncMock(
        return_value=SimpleNamespace(output="Checked the source; kept the page.")
    )
    monkeypatch.setattr(
        review_module, "review_agent", lambda *args: SimpleNamespace(run=run)
    )
    memory = Mock()
    namespace = Mock()
    memory.namespaces = {"episodic": namespace}
    namespace.query.return_value = SimpleNamespace(
        rows=[
            SimpleNamespace(
                model_dump=lambda **_: {"id": "source", "content": "a past account"}
            )
        ]
    )
    result = await review_module.review([], "phi", memory)
    assert result == "Checked the source; kept the page."
    assert namespace.query.call_args.kwargs["top_k"] == 20
    assert "not an exhaustive history" in run.call_args.args[0]
    assert run.call_args.kwargs["usage_limits"].tool_calls_limit == 20
    memory.store_episodic_memory.assert_not_called()


async def test_failed_memory_review_does_not_remove_daily_reflection():
    handler = MessageHandler.__new__(MessageHandler)
    agent = Mock(
        process_memory_review=AsyncMock(side_effect=OSError("offline")),
        process_reflection=AsyncMock(return_value="Quiet reflection complete"),
    )
    handler.agent = agent
    await handler.daily_reflection()
    agent.process_reflection.assert_awaited_once()
