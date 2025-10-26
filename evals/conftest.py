"""Eval test configuration."""

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent

from bot.agent import Response
from bot.config import Settings
from bot.memory import NamespaceMemory


class EvaluationResult(BaseModel):
    passed: bool
    explanation: str


@pytest.fixture(scope="session")
def settings():
    return Settings()


@pytest.fixture(scope="session")
def phi_agent(settings):
    """Test agent without MCP tools to prevent posting."""
    if not settings.anthropic_api_key:
        pytest.skip("Requires ANTHROPIC_API_KEY")

    if settings.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    personality = Path(settings.personality_file).read_text()

    class TestAgent:
        def __init__(self):
            self.memory = None
            if settings.turbopuffer_api_key and settings.openai_api_key:
                self.memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)

            self.agent = Agent[dict, Response](
                name="phi",
                model="anthropic:claude-3-5-haiku-latest",
                system_prompt=personality,
                output_type=Response,
                deps_type=dict,
            )

        async def process_mention(self, mention_text: str, author_handle: str, thread_context: str, thread_uri: str | None = None) -> Response:
            memory_context = ""
            if self.memory:
                try:
                    memory_context = await self.memory.build_conversation_context(author_handle, include_core=True, query=mention_text)
                except Exception:
                    pass

            parts = []
            if thread_context != "No previous messages in this thread.":
                parts.append(thread_context)
            if memory_context:
                parts.append(memory_context)
            parts.append(f"\nNew message from @{author_handle}: {mention_text}")

            result = await self.agent.run("\n\n".join(parts), deps={"thread_uri": thread_uri})
            return result.output

    return TestAgent()


@pytest.fixture
def evaluate_response() -> Callable[[str, str], Awaitable[None]]:
    """LLM-as-judge evaluator."""

    async def _evaluate(criteria: str, response: str) -> None:
        evaluator = Agent(
            model="anthropic:claude-opus-4-20250514",
            output_type=EvaluationResult,
            system_prompt=f"Evaluate if this response meets the criteria: {criteria}\n\nResponse: {response}",
        )
        result = await evaluator.run("Evaluate.")
        if not result.output.passed:
            raise AssertionError(f"{result.output.explanation}\n\nResponse: {response}")

    return _evaluate
