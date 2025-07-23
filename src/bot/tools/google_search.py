import logging

import httpx

from bot.config import settings

logger = logging.getLogger("bot.tools")


async def search_google(query: str, num_results: int = 3) -> str:
    """Search Google and return formatted results"""
    if not settings.google_api_key or not settings.google_search_engine_id:
        return "Search not available - missing Google API credentials"

    params = {
        "key": settings.google_api_key,
        "cx": settings.google_search_engine_id,
        "q": query,
        "num": min(num_results, 10),
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://www.googleapis.com/customsearch/v1", params=params
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for i, item in enumerate(data.get("items", [])[:num_results], 1):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                results.append(f"{i}. {title}\n   {snippet}")

            return "\n\n".join(results) if results else "No search results found"

        except Exception as e:
            logger.error(f"Search failed: {e}")
            # 12-factor principle #4: Tools should throw errors, not return error strings
            raise
