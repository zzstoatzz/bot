"""Demonstrate that search tool is actually being used"""

import asyncio
import os

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from bot.config import settings


class Response(BaseModel):
    text: str = Field(description="Response text")


async def test_tool_proof():
    """Prove the search tool is being used by tracking calls"""

    if not settings.anthropic_api_key:
        print("❌ No Anthropic API key")
        return

    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    # Track what the agent does
    tool_calls = []

    # Create agent
    agent = Agent(
        "anthropic:claude-3-5-haiku-latest",
        system_prompt="You help answer questions accurately.",
        output_type=Response,
    )

    # Add a search tool that returns a unique string
    @agent.tool
    async def search_web(ctx: RunContext[None], query: str) -> str:
        """Search the web for information"""
        tool_calls.append(query)
        # Return a unique string that proves the tool was called
        return f"UNIQUE_SEARCH_RESULT_12345: Found information about {query}"

    print("🧪 Testing if agent uses search tool...\n")

    # Test 1: Should NOT use tool
    print("Test 1: Simple math (should not search)")
    result = await agent.run("What is 5 + 5?")
    print(f"Response: {result.output.text}")
    print(f"Tool called: {'Yes' if tool_calls else 'No'}")
    print()

    # Test 2: SHOULD use tool
    print("Test 2: Current events (should search)")
    result = await agent.run("What's the latest news about AI?")
    print(f"Response: {result.output.text}")
    print(f"Tool called: {'Yes' if len(tool_calls) > 0 else 'No'}")
    if tool_calls:
        print(f"Search query: {tool_calls[-1]}")

    # Check if our unique string is in the response
    if "UNIQUE_SEARCH_RESULT_12345" in result.output.text:
        print("❌ Tool result leaked into output!")
    else:
        print("✅ Tool result properly integrated")

    print(f"\nTotal tool calls: {len(tool_calls)}")


if __name__ == "__main__":
    asyncio.run(test_tool_proof())
