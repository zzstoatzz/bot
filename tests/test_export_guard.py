"""A write in a run that loaded permissioned material is compared against it."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import ToolDefinition

from bot.config import settings
from bot.core import export_guard, mcp_guard
from bot.core.export_guard import ExportGuard, Finding, Permissioned, needs_review
from bot.core.mcp_guard import make_mcp_guard

OPERATOR = "did:plc:operator"
DM = Permissioned("private operator conversation", "the secret", frozenset({OPERATOR}))
SPACE = Permissioned("at://space/record", "members only", frozenset({"did:plc:other"}))


@pytest.fixture(autouse=True)
def operator(monkeypatch):
    monkeypatch.setattr(settings, "owner_did", OPERATOR)


def reviewer(monkeypatch, finding: Finding | Exception) -> AsyncMock:
    run = AsyncMock(
        side_effect=finding if isinstance(finding, Exception) else None,
        return_value=SimpleNamespace(output=finding),
    )
    monkeypatch.setattr(export_guard, "_get_reviewer", lambda: SimpleNamespace(run=run))
    return run


@pytest.mark.parametrize(
    "tool,mutation,loaded,expected",
    [
        ("update_goal_progress", True, [], []),
        ("search_memory", False, [DM], []),
        ("update_goal_progress", True, [DM], [DM]),
        ("reply_operator_dm", True, [DM, SPACE], [SPACE]),
        ("post", True, [DM], []),
        ("save_memory", True, [DM], []),
    ],
    ids=[
        "nothing loaded",
        "a read",
        "a public write",
        "the operator may read his own conversation, not another space",
        "post is reviewed by the policy gate",
        "save_memory declines by itself",
    ],
)
def test_which_loaded_items_a_write_could_carry(tool, mutation, loaded, expected):
    assert needs_review(tool, loaded, mutation=mutation) == expected


async def test_a_disclosing_write_is_refused_with_the_reason(monkeypatch):
    run = reviewer(monkeypatch, Finding(discloses=True, reason="Leave out the plan."))

    refusal = await export_guard.review("write_self", {"text": "the secret"}, [DM])

    assert refusal is not None
    assert "write_self did not run" in refusal and "Leave out the plan." in refusal
    assert run.await_args is not None
    prompt = run.await_args.args[0]
    assert "the secret" in prompt and "private operator conversation" in prompt


async def test_a_clean_write_passes(monkeypatch):
    reviewer(monkeypatch, Finding(discloses=False, reason="Unrelated."))
    assert await export_guard.review("write_self", {"text": "hello"}, [DM]) is None


async def test_no_review_means_no_write(monkeypatch):
    reviewer(monkeypatch, RuntimeError("judge is down"))
    refusal = await export_guard.review("write_self", {"text": "hello"}, [DM])
    assert refusal is not None and "review is unavailable" in refusal


async def _execute(tool: str, permissioned: list[Permissioned]):
    handler = AsyncMock(return_value="done")
    result = await ExportGuard().wrap_tool_execute(
        RunContext(
            deps=SimpleNamespace(permissioned=permissioned),
            model=TestModel(),
            usage=RunUsage(),
        ),
        call=ToolCallPart(tool),
        tool_def=ToolDefinition(name=tool),
        args={"text": "x"},
        handler=handler,
    )
    return result, handler


async def test_a_native_write_does_not_run_when_refused(monkeypatch):
    review = AsyncMock(return_value="refused")
    monkeypatch.setattr(export_guard, "review", review)

    result, handler = await _execute("update_goal_progress", [DM])

    assert result == "refused"
    handler.assert_not_awaited()


@pytest.mark.parametrize(
    "tool,permissioned",
    [("search_memory", [DM]), ("update_goal_progress", []), ("reply_operator_dm", [DM])],
)
async def test_reads_and_untainted_runs_are_not_reviewed(
    monkeypatch, tool, permissioned
):
    review = AsyncMock(return_value="refused")
    monkeypatch.setattr(export_guard, "review", review)

    result, handler = await _execute(tool, permissioned)

    assert result == "done"
    review.assert_not_awaited()


async def test_an_mcp_write_is_reviewed_and_a_read_is_not(monkeypatch):
    monkeypatch.setattr(
        mcp_guard, "get_override", AsyncMock(return_value={"active": False})
    )
    review = AsyncMock(return_value="refused")
    monkeypatch.setattr(export_guard, "review", review)
    ctx = SimpleNamespace(deps=SimpleNamespace(permissioned=[DM], memory=None))
    call_tool = AsyncMock(return_value="ok")
    guard = make_mcp_guard("tangled", "operator-dm")

    assert await guard(ctx, call_tool, "create_issue", {"title": "x"}) == "refused"
    call_tool.assert_not_awaited()

    await guard(ctx, call_tool, "read_file", {"path": "README.md"})
    call_tool.assert_awaited_once()
    review.assert_awaited_once()
