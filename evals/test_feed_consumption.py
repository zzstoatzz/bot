"""Provider routing against production feed tools, held before execution."""

import pytest
from pydantic_ai import Agent, DeferredToolRequests

from bot.tools import feeds
from bot.tools._helpers import PhiDeps


@pytest.mark.parametrize(
    "prompt,name",
    [
        ("Read my following timeline.", "timeline"),
        ("Read my own custom feed with slug jazz-vibes.", "jazz-vibes"),
    ],
)
async def test_selects_current_feed_reader(settings, monkeypatch, prompt, name):
    if not settings.anthropic_api_key and not settings.openai_api_key:
        raise pytest.skip.Exception("Requires a model API key")
    for variable, value in (
        ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        ("OPENAI_API_KEY", settings.openai_api_key),
    ):
        if value:
            monkeypatch.setenv(variable, value)
    agent = Agent[PhiDeps, str | DeferredToolRequests](
        settings.agent_model, deps_type=PhiDeps, output_type=[str, DeferredToolRequests]
    )
    feeds.register(agent)
    for tool in agent._function_toolset.tools.values():
        tool.requires_approval = True
    result = await agent.run(prompt, deps=PhiDeps(author_handle=settings.owner_handle))
    assert isinstance(result.output, DeferredToolRequests), result.output
    calls = result.output.approvals
    assert len(calls) == 1 and calls[0].tool_name == "read_feed"
    assert calls[0].args_as_dict().get("name", "timeline") == name
