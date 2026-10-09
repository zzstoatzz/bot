"""Eval test configuration.

The eval test agents define their own structured `Response` output type
locally — production phi (in bot.agent) was migrated to a tool-based
action layer where side effects happen via tool calls and the agent run
returns a plain summary string. The eval fixtures predate that migration
and still want a structured-output shape so individual eval tests can
make assertions on response.action / response.text. Keeping it local to
the eval harness keeps the production code clean of vestigial action shapes.
"""

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from bot.config import Settings
from bot.memory import NamespaceMemory


class Response(BaseModel):
    """Structured response shape used by the eval test agents only."""

    action: str = Field(description="reply, like, repost, post, or ignore")
    text: str | None = Field(
        default=None, description="response text when action is reply or post"
    )
    reason: str | None = Field(
        default=None, description="brief reason when action is ignore"
    )


class EvaluationResult(BaseModel):
    # explanation first so the judge reasons before committing to a verdict —
    # with passed first it emits the bool cold, then sometimes argues the
    # opposite in the explanation
    explanation: str
    passed: bool


@pytest.fixture(scope="session")
def settings():
    return Settings()


@pytest.fixture(scope="session")
def phi_agent(settings):
    """Test agent without MCP tools to prevent posting."""
    if not settings.anthropic_api_key:
        raise pytest.skip.Exception("Requires ANTHROPIC_API_KEY")

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
                model="anthropic:claude-haiku-4-5-20251001",
                system_prompt=personality,
                output_type=Response,
                deps_type=dict,
            )

        async def process_mention(
            self,
            mention_text: str,
            author_handle: str,
            thread_context: str,
            thread_uri: str | None = None,
        ) -> Response:
            memory_context = ""
            if self.memory:
                try:
                    memory_context = await self.memory.build_user_context(
                        author_handle, query_text=mention_text
                    )
                except Exception:
                    pass

            parts = []
            if thread_context != "No previous messages in this thread.":
                parts.append(thread_context)
            if memory_context:
                parts.append(memory_context)
            parts.append(f"\nNew message from @{author_handle}: {mention_text}")

            result = await self.agent.run(
                "\n\n".join(parts), deps={"thread_uri": thread_uri}
            )
            return result.output

    return TestAgent()


@pytest.fixture
def evaluate_response() -> Callable[[str, str], Awaitable[None]]:
    """LLM-as-judge evaluator."""

    async def _evaluate(criteria: str, response: str) -> None:
        evaluator = Agent(
            model="anthropic:claude-sonnet-4-6",
            output_type=EvaluationResult,
            system_prompt=(
                "Evaluate if this response meets the criteria. Be lenient — "
                "examples in the criteria are illustrative, not exhaustive. "
                "Pass if the response makes a reasonable attempt at the intent.\n\n"
                f"Criteria: {criteria}\n\nResponse: {response}"
            ),
        )
        result = await evaluator.run("Evaluate.")
        if not result.output.passed:
            raise AssertionError(f"{result.output.explanation}\n\nResponse: {response}")

    return _evaluate
