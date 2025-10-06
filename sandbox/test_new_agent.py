"""Test the new MCP-enabled agent."""

import asyncio

from bot.agent import PhiAgent
from bot.memory import Memory


async def main():
    """Test basic agent functionality."""
    # Create memory and agent
    memory = Memory()
    agent = PhiAgent(memory)

    # Test a simple interaction
    response = await agent.process_mention(
        mention_text="hey phi, what are you?",
        author_handle="test.user",
        thread_uri="at://test/thread/123",
    )

    print(f"Action: {response.action}")
    print(f"Text: {response.text}")
    print(f"Reason: {response.reason}")

    # Check memory was stored
    context = memory.get_thread_context("at://test/thread/123")
    print(f"\nThread context:\n{context}")


if __name__ == "__main__":
    asyncio.run(main())
