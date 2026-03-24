"""Smoke test for memory system using real .env credentials."""

import pytest

from bot.config import Settings
from bot.memory import NamespaceMemory


@pytest.fixture
async def memory():
    s = Settings()
    if not s.turbopuffer_api_key or not s.openai_api_key:
        pytest.skip("needs TURBOPUFFER_API_KEY and OPENAI_API_KEY in .env")
    mem = NamespaceMemory(api_key=s.turbopuffer_api_key)
    yield mem
    await mem.close()


async def test_build_user_context_old_namespace(memory):
    """build_user_context should not crash on namespaces without 'kind' column."""
    # this handle has old data without the kind attribute
    ctx = await memory.build_user_context(
        "zzstoatzzdevlog.bsky.social",
        query_text="hello",
        include_core=False,
    )
    print(f"\n--- context ---\n{ctx}\n---")
    assert isinstance(ctx, str)


async def test_store_and_retrieve(memory):
    """Round-trip: store interaction, then retrieve it."""
    handle = "smoke-test.example"
    await memory.store_interaction(handle, "i like rust", "rust is great!")

    ctx = await memory.build_user_context(handle, query_text="rust", include_core=False)
    print(f"\n--- context ---\n{ctx}\n---")
    assert "rust" in ctx.lower()


async def test_search_old_namespace(memory):
    """search should work on namespaces without 'kind' column."""
    results = await memory.search("zzstoatzzdevlog.bsky.social", "hello", top_k=3)
    print(f"\n--- search results ---\n{results}\n---")
    assert isinstance(results, list)


async def test_search_unified(memory):
    """search_unified returns a list from both user + episodic namespaces."""
    results = await memory.search_unified("zzstoatzzdevlog.bsky.social", "hello", top_k=3)
    print(f"\n--- unified results ---\n{results}\n---")
    assert isinstance(results, list)


async def test_search_unified_missing_user(memory):
    """search_unified works when user namespace doesn't exist (episodic-only)."""
    results = await memory.search_unified("nonexistent-user-12345.example", "hello", top_k=3)
    print(f"\n--- unified (missing user) ---\n{results}\n---")
    assert isinstance(results, list)
