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
        return RequestUsage(input_tokens=10 + len(text) + tools)


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


async def test_exact_counting_subtracts_framing_and_totals_the_whole_prompt():
    sections = _sections()
    counting, total = await count_context_tokens(CountingModel(), sections)
    assert counting == "exact"
    by_name = {s.name: s.tokens for s in sections}
    assert by_name["static_instructions"] == 40
    assert by_name["inject_now"] == 8
    assert by_name["inject_silent"] == 0
    assert by_name["post"] == len("post") + len("say it")
    # the whole-prompt count is one request carrying every section
    assert total == 10 + 40 + 8 + 1 + len("post") + len("say it")


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
