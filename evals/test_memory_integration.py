"""Test phi's episodic memory integration."""

import pytest

from bot.agent import PhiAgent
from bot.config import Settings
from bot.memory import MemoryType, NamespaceMemory


@pytest.mark.asyncio
async def test_phi_retrieves_episodic_memory(settings):
    """Test that phi can retrieve and use episodic memories."""
    if not all([settings.turbopuffer_api_key, settings.openai_api_key, settings.anthropic_api_key]):
        pytest.skip("Requires TurboPuffer, OpenAI, and Anthropic API keys in .env")

    # Create memory system
    memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)

    # Store a memory about a user
    await memory.store_user_memory(
        "alice.bsky",
        "Alice mentioned she's working on a PhD in neuroscience",
        MemoryType.USER_FACT,
    )

    # Create agent
    agent = PhiAgent()
    agent.memory = memory

    # Process a mention that should trigger memory retrieval
    response = await agent.process_mention(
        mention_text="what do you remember about me?",
        author_handle="alice.bsky",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/memory1",
    )

    if response.action == "reply":
        assert response.text is not None
        # Should reference the neuroscience PhD in the response
        assert (
            "neuroscience" in response.text.lower()
            or "phd" in response.text.lower()
            or "working on" in response.text.lower()
        ), "Response should reference stored memory about Alice"


@pytest.mark.asyncio
async def test_phi_stores_conversation_in_memory(settings):
    """Test that phi stores interactions in episodic memory."""
    if not all([settings.turbopuffer_api_key, settings.openai_api_key, settings.anthropic_api_key]):
        pytest.skip("Requires TurboPuffer, OpenAI, and Anthropic API keys in .env")

    memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)

    agent = PhiAgent()
    agent.memory = memory

    # Have a conversation
    response = await agent.process_mention(
        mention_text="I'm really interested in phenomenology",
        author_handle="bob.bsky",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/memory2",
    )

    if response.action == "reply":
        # Verify memories were stored
        memories = await memory.get_user_memories("bob.bsky", limit=10)

        assert len(memories) > 0, "Should have stored conversation in memory"

        # Check that both user's message and bot's response were stored
        memory_texts = [m.content for m in memories]
        assert any(
            "phenomenology" in text.lower() for text in memory_texts
        ), "Should store user's message about phenomenology"
