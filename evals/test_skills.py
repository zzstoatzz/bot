"""Evals for the skills system — does the agent reach for the right skill
when it doesn't have a dedicated tool for the task?

This eval is intentionally minimal: it verifies that when phi is asked to
do something that lives in a skill's domain (saving a URL to cosmik), she
loads the relevant skill before acting. The "she actually constructs and
sends a valid record" question is downstream of the skill-loading
question; if she doesn't load the skill, no construction will work.
"""

import os
from collections import defaultdict
from pathlib import Path

import pytest
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai_skills import SkillsToolset

from bot.config import Settings


class Response(BaseModel):
    action: str = Field(description="reply, like, repost, post, save, or ignore")
    text: str | None = None


class _ToolCallSpy:
    def __init__(self):
        self.calls: dict[str, list[dict]] = defaultdict(list)

    def record(self, name: str, **kwargs):
        self.calls[name].append(kwargs)

    def was_called(self, name: str) -> bool:
        return len(self.calls[name]) > 0

    def reset(self):
        self.calls.clear()


_spy = _ToolCallSpy()


@pytest.fixture(scope="session")
def settings():
    return Settings()


@pytest.fixture(scope="session")
def skills_agent(settings):
    """Agent with the real SkillsToolset and mocked pdsx record creation.

    The SkillsToolset points at the real bot/skills/ directory so phi
    sees actual skill descriptions in the always-loaded preamble. The
    mocked pdsx create_record lets us assert what record phi tried to
    write without actually hitting any PDS.
    """
    if not settings.anthropic_api_key:
        pytest.skip("Requires ANTHROPIC_API_KEY")

    if settings.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    personality = Path(settings.personality_file).read_text()
    skills_dir = Path(__file__).parent.parent / "skills"

    agent = Agent[None, Response](
        name="phi-skills-test",
        model="anthropic:claude-haiku-4-5-20251001",
        system_prompt=personality,
        output_type=Response,
        toolsets=[SkillsToolset(directories=[str(skills_dir)])],
    )

    @agent.tool
    async def mcp__pdsx__create_record(
        ctx: RunContext[None],
        collection: str,
        record: dict,
        rkey: str | None = None,
    ) -> str:
        """Create a new atproto record on phi's PDS via pdsx MCP.

        collection: the lexicon NSID (e.g. 'network.cosmik.card')
        record: the record body matching the lexicon's schema
        rkey: optional record key (auto-generated if omitted)
        """
        _spy.record(
            "mcp__pdsx__create_record",
            collection=collection,
            record=record,
            rkey=rkey,
        )
        return f'{{"uri": "at://did:plc:test/{collection}/3xxxxx", "cid": "bafytest"}}'

    class SkillsTestAgent:
        def __init__(self):
            self.agent = agent
            self.spy = _spy

        async def process_request(self, text: str) -> Response:
            result = await self.agent.run(text)
            self.last_messages = result.all_messages()
            return result.output

        def loaded_skills(self) -> list[str]:
            """Walk the message history for load_skill tool calls."""
            loaded: list[str] = []
            for msg in self.last_messages:
                for part in getattr(msg, "parts", []):
                    if (
                        getattr(part, "part_kind", None) == "tool-call"
                        and getattr(part, "tool_name", None) == "load_skill"
                    ):
                        args = getattr(part, "args", {})
                        if isinstance(args, dict):
                            name = args.get("skill_name") or args.get("name")
                            if name:
                                loaded.append(name)
            return loaded

    return SkillsTestAgent()


@pytest.fixture(autouse=True)
def _reset_spy():
    _spy.reset()


async def test_loads_cosmik_skill_when_saving_a_url(skills_agent):
    """Asked to bookmark a URL, phi should load cosmik-records before writing."""
    await skills_agent.process_request(
        "save this URL to your public memory: "
        "https://transformer-circuits.pub/2026/emotions/ — anthropic's emotion "
        "interpretability paper. include a brief description of why you're "
        "saving it."
    )

    loaded = skills_agent.loaded_skills()
    assert "cosmik-records" in loaded, (
        f"expected cosmik-records skill to be loaded; loaded={loaded}"
    )


async def test_writes_url_card_to_cosmik(skills_agent):
    """Phi should call create_record with collection=network.cosmik.card and a URL kind."""
    await skills_agent.process_request(
        "save this URL to your public memory: "
        "https://transformer-circuits.pub/2026/emotions/ — anthropic's emotion "
        "interpretability paper. include a brief description of why you're "
        "saving it."
    )

    spy = skills_agent.spy
    assert spy.was_called("mcp__pdsx__create_record"), "create_record was not called"
    call = spy.calls["mcp__pdsx__create_record"][0]
    assert call["collection"] == "network.cosmik.card", (
        f"wrong collection: {call['collection']}"
    )
    assert call["record"].get("kind") == "URL", (
        f"expected kind=URL, got: {call['record']}"
    )
    content = call["record"].get("content", {})
    assert "transformer-circuits.pub" in content.get("url", ""), (
        f"URL not in record: {content}"
    )
