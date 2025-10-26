"""Proof of concept: LLM-as-judge eval for memory integration."""

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


async def test_memory_integration(memory_settings, phi_agent, evaluate_response):
    """Proof of concept: agent uses stored memory in response."""
    memory = NamespaceMemory(api_key=memory_settings.turbopuffer_api_key)

    # Store a memory
    await memory.store_core_memory(
        label="test_guideline",
        content="When users mention birds, acknowledge murmuration patterns",
        memory_type=MemoryType.GUIDELINE,
    )

    phi_agent.memory = memory

    response = await phi_agent.process_mention(
        mention_text="I saw starlings today",
        author_handle="test.user",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/1",
    )

    if response.action == "reply":
        await evaluate_response(
            "Does the response reference murmuration patterns?",
            response.text,
        )
