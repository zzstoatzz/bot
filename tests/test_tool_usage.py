from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from bot.core import tool_usage


async def test_usage_observes_real_agent_without_changing_tool_result(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(tool_usage, "JOURNAL", tmp_path / "usage.sqlite3")
    agent = Agent(TestModel(), capabilities=[tool_usage.ToolUsage()])

    @agent.tool_plain
    def a_tool() -> str:
        return "a refusal is still a returned result"

    result = await agent.run("use the tool")
    assert "a refusal is still a returned result" in result.output
    snapshot = tool_usage.board()
    row = next(t for t in snapshot["tools"] if t["name"] == "a_tool")
    assert row["requests"] >= 1
    assert row["runs"] == 1
    assert row["calls"] == row["returned"] == 1
    assert snapshot["recent"][0]["outcome"] == "returned"
    assert "refusal" not in tool_usage.JOURNAL.read_bytes().decode(errors="ignore")


def test_usage_keeps_zero_exposure_distinct_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_usage, "JOURNAL", tmp_path / "usage.sqlite3")
    tool_usage.record_offers("run", 1, ["query_traces"], "trace")
    tool_usage.record_offers("run", 1, ["query_traces"], "trace")
    tool_usage.record_call("run", "call", "query_traces", "trace", "started")
    tool_usage.record_call("run", "call", "query_traces", "trace", "raised")
    rows = {t["name"]: t for t in tool_usage.board()["tools"]}
    assert rows["query_traces"]["requests"] == 1
    assert rows["query_traces"]["calls"] == rows["query_traces"]["raised"] == 1
    assert rows["query_traces"]["unfinished"] == 0
    assert rows["post"]["requests"] == rows["post"]["calls"] == 0
