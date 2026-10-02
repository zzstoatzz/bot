"""Regression test: an unreachable MCP server degrades to a missing toolset.

2026-07-17: a 403 from the logfire MCP (wrong token kind) killed entire
agent runs at toolset-enter time — the daily reflection died on a toolset
it never needed. _run_agent must drop toolsets that fail to connect and
run with the rest.

2026-10-01: pdsx connected, then answered 502 to the first tools/list. The
MCP client raises that in a background task group, which cancels the run and
surfaces only when the exit stack unwinds, past the connect-time guard. The
editorial pass died in 0.3s and no article went out. A run that fails on an
MCP transport error before the model has answered is retried.
"""

import json
from unittest.mock import Mock, patch

import httpx
import pytest
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from bot import agent as agent_module
from bot.agent import PhiAgent
from bot.tools._helpers import PhiDeps


class _GoodToolset:
    label = "good"
    entered = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *exc):
        return None


class _DeadToolset:
    label = "dead"

    async def __aenter__(self):
        raise RuntimeError("403 Forbidden")

    async def __aexit__(self, *exc):
        return None


async def test_dead_mcp_toolset_does_not_kill_run():
    phi = PhiAgent.__new__(PhiAgent)  # skip __init__ — only _run_agent matters
    good, dead = _GoodToolset(), _DeadToolset()
    seen: dict = {}

    class _FakeResult:
        output = "ran fine"

    async def fake_run(prompt, deps=None, toolsets=None, usage=None):
        seen["toolsets"] = toolsets
        return _FakeResult()

    phi.agent = Mock(run=fake_run)
    with (
        patch.object(PhiAgent, "_mcp_toolsets", return_value=[dead, good]),
    ):
        out = await phi._run_agent(
            label="test run", prompt="hi", deps=PhiDeps(author_handle="")
        )

    assert out == "ran fine"
    assert seen["toolsets"] == [good]
    assert good.entered


FLAKY_URL = "http://flaky.test/mcp"


class _FlakyMCP:
    """An MCP server that connects, then 502s its first `failures` tools/list calls."""

    def __init__(self, failures: int):
        self.failures = failures
        self.lists = 0

    def _respond(self, request: httpx.Request) -> httpx.Response:
        if request.method != "POST":
            return httpx.Response(405)
        body = json.loads(request.content)
        if "id" not in body:
            return httpx.Response(202)
        if body["method"] == "initialize":
            result = {
                "protocolVersion": body["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "flaky", "version": "0"},
            }
        else:
            self.lists += 1
            if self.lists <= self.failures:
                return httpx.Response(502, text="Bad Gateway")
            result = {"tools": []}
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": result}
        )

    def toolset(self) -> MCPServerStreamableHTTP:
        return MCPServerStreamableHTTP(
            url=FLAKY_URL,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(self._respond)),
        )


def _phi_with(server: _FlakyMCP) -> tuple[PhiAgent, list[list]]:
    phi = PhiAgent.__new__(PhiAgent)
    real = Agent(TestModel(), deps_type=PhiDeps)
    offered: list[list] = []

    async def run(prompt, **kwargs):
        offered.append(kwargs["toolsets"])
        return await real.run(prompt, **kwargs)

    phi.agent = Mock(run=run)
    return phi, offered


@pytest.fixture
def no_retry_pause(monkeypatch):
    monkeypatch.setattr(agent_module, "MCP_RETRY_PAUSE_S", 0)


async def test_mcp_502_after_connect_is_retried(no_retry_pause):
    server = _FlakyMCP(failures=1)
    phi, offered = _phi_with(server)
    with patch.object(
        PhiAgent, "_mcp_toolsets", side_effect=lambda **_: [server.toolset()]
    ):
        out = await phi._run_agent(
            label="editorial", prompt="hi", deps=PhiDeps(author_handle="")
        )

    assert out == "success (no tool calls)"
    assert [len(ts) for ts in offered] == [1, 1]


async def test_mcp_server_that_keeps_failing_is_dropped(no_retry_pause):
    server = _FlakyMCP(failures=99)
    phi, offered = _phi_with(server)
    with patch.object(
        PhiAgent, "_mcp_toolsets", side_effect=lambda **_: [server.toolset()]
    ):
        out = await phi._run_agent(
            label="editorial", prompt="hi", deps=PhiDeps(author_handle="")
        )

    assert out == "success (no tool calls)"
    assert [len(ts) for ts in offered] == [1, 1, 0]


async def test_mcp_failure_after_the_model_answered_is_not_retried(no_retry_pause):
    """Once the model has answered, tools may have acted; rerunning could repeat them."""
    phi = PhiAgent.__new__(PhiAgent)
    calls = 0

    async def run(prompt, *, usage: RunUsage, **_):
        nonlocal calls
        calls += 1
        usage.requests = 1
        request = httpx.Request("POST", FLAKY_URL)
        raise ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [
                httpx.HTTPStatusError(
                    "502",
                    request=request,
                    response=httpx.Response(502, request=request),
                )
            ],
        )

    phi.agent = Mock(run=run)
    server = _FlakyMCP(failures=0)
    with patch.object(
        PhiAgent, "_mcp_toolsets", side_effect=lambda **_: [server.toolset()]
    ):
        out = await phi._run_agent(
            label="editorial", prompt="hi", deps=PhiDeps(author_handle="")
        )

    assert out.startswith("editorial failed: ExceptionGroup")
    assert calls == 1


class TestQueryTraces:
    """query_traces guards: select-only, columnar rendering."""

    def test_render_columnar(self):
        from bot.tools.traces import _render_columnar

        out = _render_columnar(
            {
                "columns": [
                    {"name": "tool", "values": ["post", "query"]},
                    {"name": "n", "values": [3, 1]},
                ]
            }
        )
        assert out.splitlines() == ["tool | n", "post | 3", "query | 1"]
        assert _render_columnar({"columns": []}) == "no rows"


async def test_filtered_mcp_server_is_still_retried(no_retry_pause):
    """The retry finds a failed server by URL, through the filter wrapped around it."""
    server = _FlakyMCP(failures=1)
    phi, offered = _phi_with(server)
    filtered = lambda **_: [server.toolset().filtered(lambda _ctx, _tool: True)]  # noqa: E731
    with patch.object(PhiAgent, "_mcp_toolsets", side_effect=filtered):
        out = await phi._run_agent(
            label="editorial", prompt="hi", deps=PhiDeps(author_handle="")
        )

    assert out == "success (no tool calls)"
    assert [len(ts) for ts in offered] == [1, 1]
