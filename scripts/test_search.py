"""Test search functionality"""

import asyncio
from bot.tools.google_search import GoogleSearchTool
from bot.config import settings


async def test_search():
    """Test Google search tool"""
    if not settings.google_api_key:
        print("❌ No Google API key configured")
        print("   Add GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID to .env")
        return

    search = GoogleSearchTool()

    queries = [
        "integrated information theory consciousness",
        "latest AI research 2025",
        "Bluesky AT Protocol",
    ]

    for query in queries:
        print(f"\nSearching for: {query}")
        print("-" * 50)

        results = await search.search(query)
        if results:
            print(search.format_results(results))
        else:
            print("No results found")


if __name__ == "__main__":
    asyncio.run(test_search())
