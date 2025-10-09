"""Test phi's episodic memory integration."""

import pytest

from bot.config import Settings
from bot.memory import MemoryType, NamespaceMemory


@pytest.fixture
def memory_settings():
    """Check if memory keys are available."""
    settings = Settings()
    if not all([settings.turbopuffer_api_key, settings.openai_api_key, settings.anthropic_api_key]):
        pytest.skip("Requires TURBOPUFFER_API_KEY, OPENAI_API_KEY, and ANTHROPIC_API_KEY")
    return settings


async def test_core_memory_integration(memory_settings, phi_agent, evaluate_response):
    """Test that phi uses core memories in responses."""
    memory = NamespaceMemory(api_key=memory_settings.turbopuffer_api_key)

    # Store a core memory
    await memory.store_core_memory(
        label="test_interaction_rule",
        content="When users mention birds, always acknowledge the beauty of murmuration patterns",
        memory_type=MemoryType.GUIDELINE,
    )

    # Override agent's memory with our test memory
    phi_agent.memory = memory

    # Ask about birds
    response = await phi_agent.process_mention(
        mention_text="I saw a huge flock of starlings today",
        author_handle="test.user",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/1",
    )

    if response.action == "reply":
        await evaluate_response(
            "Does the response acknowledge or reference murmuration patterns?",
            response.text,
        )


async def test_user_memory_integration(memory_settings, phi_agent, evaluate_response):
    """Test that phi uses user-specific memories in responses."""
    memory = NamespaceMemory(api_key=memory_settings.turbopuffer_api_key)

    # Store a memory about a user
    await memory.store_user_memory(
        handle="alice.test",
        content="Alice is researching swarm intelligence in biological systems",
        memory_type=MemoryType.USER_FACT,
    )

    # Override agent's memory
    phi_agent.memory = memory

    # User asks a question
    response = await phi_agent.process_mention(
        mention_text="what do you remember about my research?",
        author_handle="alice.test",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/2",
    )

    if response.action == "reply":
        await evaluate_response(
            "Does the response reference Alice's research on swarm intelligence or biological systems?",
            response.text,
        )
