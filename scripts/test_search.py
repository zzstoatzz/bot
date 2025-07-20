"""Test search functionality"""

import asyncio

from bot.config import settings
from bot.tools.google_search import search_google


async def test_search():
    """Test Google search function"""
    if not settings.google_api_key:
        print("❌ No Google API key configured")
        print("   Add GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID to .env")
        return

    queries = [
        "integrated information theory consciousness",
        "latest AI research 2025",
        "Bluesky AT Protocol",
    ]

    for query in queries:
        print(f"\nSearching for: {query}")
        print("-" * 50)

        results = await search_google(query)
        print(results)


if __name__ == "__main__":
    asyncio.run(test_search())
