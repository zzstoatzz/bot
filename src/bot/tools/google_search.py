import asyncio
from typing import List, Dict, Optional
import httpx
from pydantic import BaseModel
from bot.config import settings


class SearchResult(BaseModel):
    title: str
    link: str
    snippet: str


class GoogleSearchTool:
    def __init__(self):
        self.api_key = settings.google_api_key
        self.search_engine_id = settings.google_search_engine_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    async def search(self, query: str, num_results: int = 3) -> List[SearchResult]:
        if not self.api_key or not self.search_engine_id:
            return []

        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": min(num_results, 10),  # Google limits to 10 per request
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("items", []):
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            link=item.get("link", ""),
                            snippet=item.get("snippet", ""),
                        )
                    )

                return results

            except Exception as e:
                print(f"Search error: {e}")
                return []

    def format_results(self, results: List[SearchResult]) -> str:
        if not results:
            return "No search results found."

        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"{i}. {result.title}\n   {result.snippet}")

        return "\n\n".join(formatted)
