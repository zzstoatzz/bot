"""Test agent with search capability"""

import asyncio
from bot.agents.anthropic_agent import AnthropicAgent
from bot.config import settings


async def test_agent_search():
    """Test that the agent can use search"""
    if not settings.anthropic_api_key:
        print("❌ No Anthropic API key configured")
        return

    agent = AnthropicAgent()

    # Test queries that might trigger search
    test_mentions = [
        "What's the latest news about AI safety?",
        "Can you search for information about quantum computing breakthroughs?",
        "What happened in tech news today?",
        "Tell me about integrated information theory",
    ]

    for mention in test_mentions:
        print(f"\nUser: {mention}")
        response = await agent.generate_response(
            mention_text=mention, author_handle="test.user"
        )
        print(f"Bot: {response}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(test_agent_search())
