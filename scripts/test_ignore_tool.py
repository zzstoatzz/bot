"""Test the ignore notification tool"""

import asyncio

from bot.agents.anthropic_agent import AnthropicAgent


async def test_ignore_tool():
    """Test that the ignore tool works correctly"""
    agent = AnthropicAgent()

    # Test scenarios where the bot should ignore
    test_cases = [
        {
            "thread_context": "alice.bsky: Hey @bob.bsky, how's your project going?\nbob.bsky: It's going great! Almost done with the backend.",
            "new_message": "alice.bsky said: @bob.bsky that's awesome! What framework are you using?",
            "author": "alice.bsky",
            "description": "Conversation between two other people",
        },
        {
            "thread_context": "",
            "new_message": "spambot.bsky said: 🎰 WIN BIG!!! Click here for FREE MONEY 💰💰💰",
            "author": "spambot.bsky",
            "description": "Obvious spam",
        },
    ]

    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {test['description']}")
        print(f"Message: {test['new_message']}")

        response = await agent.generate_response(
            mention_text=test["new_message"],
            author_handle=test["author"],
            thread_context=test["thread_context"],
        )

        print(f"Response: {response}")

        if response.startswith("IGNORED_NOTIFICATION::"):
            parts = response.split("::")
            print(f"✅ Correctly ignored! Category: {parts[1]}, Reason: {parts[2]}")
        else:
            print(f"📝 Bot responded with: {response}")


if __name__ == "__main__":
    asyncio.run(test_ignore_tool())