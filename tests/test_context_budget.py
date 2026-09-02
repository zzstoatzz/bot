"""The context budget: what the next run would send, weighed.

The panel on /operator must never present an estimate as a measurement
and never guess a model's window. These pin the two sources of truth:
the catalog lookup (both key spellings, bundled fallback, honest unknown)
and token counting (exact when the model counts, estimated otherwise,
always flagged), plus the section arithmetic the panel's bar relies on.
"""

from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import RequestUsage

from bot.core import model_catalog as mc
from bot.core.context_tokens import (
    ContextSection,
    count_context_tokens,
    estimate_tokens,
    tool_section,
)


def _catalog(models: dict[str, dict], source: str = "test") -> mc.ModelCatalog:
    cat = mc.ModelCatalog()
    cat._models = models
    cat._source = source
    cat._fetched_at = float("inf")
    return cat


async def test_catalog_resolves_both_key_spellings():
    cat = _catalog(
        {
            "anthropic/claude-sonnet-5": {"max_input_tokens": 1_000_000},
            "gpt-5.6-luna": {"max_input_tokens": 922_000},
        }
    )
    a = await cat.lookup("anthropic:claude-sonnet-5")
    assert (a.provider, a.name, a.max_input_tokens) == (
        "anthropic",
        "claude-sonnet-5",
        1_000_000,
    )
    b = await cat.lookup("openai-responses:gpt-5.6-luna")
    assert (b.provider, b.max_input_tokens) == ("openai", 922_000)


async def test_catalog_says_unknown_rather_than_guessing():
    cat = _catalog({"claude-sonnet-5": {"max_input_tokens": 1_000_000}})
    limits = await cat.lookup("anthropic:claude-made-up-9")
    assert limits.max_input_tokens is None
    assert limits.source == "unknown"


async def test_catalog_falls_back_to_the_bundled_snapshot(monkeypatch):
    class Boom:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            raise OSError("offline")

    monkeypatch.setattr(mc.httpx, "AsyncClient", Boom)
    cat = mc.ModelCatalog()
    limits = await cat.lookup("anthropic:claude-sonnet-5")
    assert limits.source == "bundled snapshot"
    assert limits.max_input_tokens == 1_000_000


class CountingModel:
    """counts like a provider would: characters, plus fixed framing."""

    calls = 0

    async def count_tokens(
        self, messages, model_settings, params: ModelRequestParameters
    ):
        CountingModel.calls += 1
        text = "".join(
            str(getattr(p, "content", "")) for m in messages for p in m.parts
        )
        tools = sum(
            len(t.name) + len(t.description or "") for t in params.function_tools
        )
        # a provider charges a fixed preamble whenever any tool is present
        framing = 100 if params.function_tools else 0
        return RequestUsage(input_tokens=10 + len(text) + tools + framing)


class SilentModel:
    async def count_tokens(self, messages, model_settings, params):
        raise NotImplementedError


def _sections() -> list[ContextSection]:
    return [
        ContextSection(
            kind="static", name="static_instructions", chars=40, text="a" * 40
        ),
        ContextSection(kind="block", name="inject_now", chars=8, text="b" * 8),
        ContextSection(kind="block", name="inject_silent", chars=0, text=""),
        tool_section(ToolDefinition(name="post", description="say it"), "function"),
    ]


async def test_exact_counting_is_marginal_and_sums_to_the_total():
    sections = _sections()
    counting, total = await count_context_tokens(CountingModel(), sections)
    assert counting == "exact"
    by_name = {s.name: s.tokens for s in sections}
    assert by_name["static_instructions"] == 40
    assert by_name["inject_now"] == 8
    assert by_name["inject_silent"] == 0
    # the tool pays for itself; the provider's preamble is its own row
    assert by_name["post"] == len("post") + len("say it")
    assert by_name["tool-use framing"] == 100
    assert sum(s.tokens for s in sections) == total - (10 + 1)
    assert total == 10 + 1 + 40 + 8 + len("post") + len("say it") + 100


async def test_estimate_when_the_model_cannot_count():
    sections = _sections()
    counting, total = await count_context_tokens(SilentModel(), sections)
    assert counting == "estimated"
    assert [s.tokens for s in sections][:3] == [10, 2, 0]
    assert total == sum(s.tokens for s in sections)
    assert (
        estimate_tokens(0) == 0 and estimate_tokens(1) == 1 and estimate_tokens(9) == 3
    )


async def test_estimate_when_no_model():
    sections = _sections()
    counting, _ = await count_context_tokens(None, sections)
    assert counting == "estimated"


def test_tool_section_carries_the_schema_the_model_sees():
    td = ToolDefinition(
        name="recall",
        description="remember",
        parameters_json_schema={
            "type": "object",
            "properties": {"q": {"type": "string"}},
        },
    )
    s = tool_section(td, "mcp:pdsx")
    assert s.kind == "tool" and s.origin == "mcp:pdsx"
    assert '"q"' in s.text and s.chars == len(s.text)
    assert s.as_dict()["origin"] == "mcp:pdsx"
    assert "text" not in s.as_dict()


async def test_tool_listing_walks_function_and_skills_toolsets(monkeypatch):
    """the listing must hand toolsets a real RunContext — they `replace()`
    it per tool and read `retries` (2026-09-02: a namespace stand-in
    500ed the endpoint in prod)."""
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.toolsets import FunctionToolset

    from bot.agent import PhiAgent

    phi = PhiAgent.__new__(PhiAgent)
    phi.memory = None
    phi.agent = Agent(model=TestModel())

    @phi.agent.tool_plain
    def post(text: str) -> str:
        """say it"""
        return text

    skills = FunctionToolset()

    @skills.tool_plain
    def read_skill(name: str) -> str:
        """read one"""
        return name

    phi.skills_toolset = skills
    monkeypatch.setattr(phi, "_mcp_toolsets", lambda run_label="": [])

    listed = await phi.list_tool_definitions()
    assert [(o, t.name) for o, t in listed] == [
        ("function", "post"),
        ("skills", "read_skill"),
    ]


def test_budget_endpoint_serves_the_snapshot_and_recomputes_only_on_refresh(
    monkeypatch,
):
    """the page must never trigger a composition by loading; the server
    keeps a snapshot and only POST /refresh (or the schedule) recomposes."""
    from unittest.mock import AsyncMock, Mock

    from starlette.testclient import TestClient

    import bot.main as m

    client = TestClient(m.app)
    agent = Mock()
    agent.render_context_budget = AsyncMock(return_value={"totals": {"prompt": 1}})
    poller = Mock()
    poller.handler = Mock()
    poller.handler.agent = agent
    monkeypatch.setattr(m.app.state, "poller", poller, raising=False)
    monkeypatch.setattr(m, "_context_budget", None)

    assert client.get("/api/context/budget").status_code == 202
    assert agent.render_context_budget.await_count == 0

    assert client.post("/api/context/budget/refresh").json() == {
        "totals": {"prompt": 1}
    }
    assert agent.render_context_budget.await_count == 1

    assert client.get("/api/context/budget").json() == {"totals": {"prompt": 1}}
    assert agent.render_context_budget.await_count == 1


def test_request_sizes_come_from_observed_runs():
    from datetime import UTC, datetime

    from bot.core.cache_stability import CacheMonitor, RequestSample, RunRecord

    mon = CacheMonitor.__new__(CacheMonitor)
    from collections import deque

    mon.runs = deque()
    assert mon.request_sizes() is None

    def run(label, sizes):
        r = RunRecord(label=label, started_at=datetime.now(UTC))
        for n in sizes:
            r.samples.append(
                RequestSample(
                    at=datetime.now(UTC),
                    model="m",
                    input_tokens=n,
                    cache_read=0,
                    cache_write=0,
                    gap_seconds=None,
                )
            )
        return r

    mon.runs.append(run("a", [90, 120, 300]))
    mon.runs.append(run("b", [80, 100]))
    mon.runs.append(RunRecord(label="empty", started_at=datetime.now(UTC)))
    sizes = mon.request_sizes()
    assert sizes == {
        "runs": 2,
        "requests": 5,
        "first_mean": 85,
        "first_max": 90,
        "p50": 100,
        "p90": 300,
        "max": 300,
    }
