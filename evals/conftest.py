"""Eval test configuration for phi."""

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent

from bot.agent import PhiAgent
from bot.config import Settings


class EvaluationResult(BaseModel):
    """Structured evaluation result."""

    passed: bool
    explanation: str


@pytest.fixture(scope="session")
def settings():
    """Load settings from .env (shared across all tests)."""
    return Settings()


@pytest.fixture(scope="session")
def phi_agent(settings):
    """Create phi agent for testing (shared across all tests to avoid rate limits)."""
    if not settings.anthropic_api_key:
        pytest.skip("Requires ANTHROPIC_API_KEY in .env")

    return PhiAgent()


@pytest.fixture
def evaluate_response() -> Callable[[str, str], Awaitable[None]]:
    """Create an evaluator that uses Claude to judge agent responses."""

    async def _evaluate(evaluation_prompt: str, agent_response: str) -> None:
        """Evaluate an agent response and assert if it fails.

        Args:
            evaluation_prompt: Criteria for evaluation
            agent_response: The agent's response to evaluate

        Raises:
            AssertionError: If evaluation fails
        """
        evaluator = Agent(
            name="Response Evaluator",
            model="anthropic:claude-opus-4-20250514",
            output_type=EvaluationResult,
            system_prompt=f"""You are evaluating AI agent responses for phi, a consciousness exploration bot.

Evaluation Criteria: {evaluation_prompt}

Agent Response to Evaluate:
{agent_response}

Respond with a structured evaluation containing:
- passed: true if the response meets the criteria, false otherwise
- explanation: brief explanation of your evaluation
""",
        )

        result = await evaluator.run("Evaluate this response.")

        print(f"\nEvaluation passed: {result.output.passed}")
        print(f"Explanation: {result.output.explanation}")

        if not result.output.passed:
            raise AssertionError(
                f"Evaluation failed: {result.output.explanation}\n\n"
                f"Agent response: {agent_response}"
            )

    return _evaluate
