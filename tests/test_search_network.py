"""Tests for the search_network tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx


async def _search_network(query: str) -> str:
    """Extracted search_network logic matching agent.py implementation."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://api.semble.so/api/search/semantic",
                params={"query": query, "limit": 10},
            )
            r.raise_for_status()
            data = r.json()

        # response is {urls: [...], pagination: {...}}
        items = data.get("urls") if isinstance(data, dict) else data
        if not items:
            return f"no network results for '{query}'"

        lines = []
        for item in items:
            meta = item.get("metadata", {})
            title = meta.get("title") or item.get("title") or "untitled"
            url = item.get("url", "")
            saves = item.get("urlLibraryCount") or 0
            desc = meta.get("description") or ""
            line = f"{title}"
            if url:
                line += f" — {url}"
            if saves:
                line += f" ({saves} saves)"
            if desc:
                line += f"\n  {desc[:200]}"
            lines.append(line)
        return "\n\n".join(lines)
    except Exception as e:
        return f"network search failed: {e}"


def _mock_response(status_code: int, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {"urls": []}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


def _semble_response(items):
    """Wrap items in semble's {urls: [...], pagination: {...}} envelope."""
    return {
        "urls": items,
        "pagination": {
            "currentPage": 1,
            "totalPages": 1,
            "totalCount": len(items),
            "hasMore": False,
            "limit": 10,
        },
    }


class TestSearchNetworkFormatting:
    async def test_formats_results_with_all_fields(self):
        resp = _mock_response(
            200,
            _semble_response(
                [
                    {
                        "url": "https://atproto.com",
                        "metadata": {
                            "title": "AT Protocol",
                            "description": "Federated social networking protocol",
                        },
                        "urlLibraryCount": 5,
                    },
                    {
                        "url": "https://docs.bsky.app",
                        "metadata": {
                            "title": "Bluesky Docs",
                            "description": "Documentation for Bluesky",
                        },
                        "urlLibraryCount": 3,
                    },
                ]
            ),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await _search_network("atproto")
        assert "AT Protocol — https://atproto.com (5 saves)" in result
        assert "Federated social networking protocol" in result
        assert "Bluesky Docs — https://docs.bsky.app (3 saves)" in result

    async def test_formats_results_with_minimal_fields(self):
        resp = _mock_response(
            200,
            _semble_response(
                [
                    {
                        "url": "https://example.com/music",
                        "metadata": {"title": "some note about music"},
                    },
                ]
            ),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await _search_network("music")
        assert "some note about music" in result
        assert "saves" not in result

    async def test_empty_results(self):
        resp = _mock_response(200, _semble_response([]))
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await _search_network("nonexistent")
        assert result == "no network results for 'nonexistent'"

    async def test_api_failure(self):
        resp = _mock_response(500)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await _search_network("anything")
        assert result.startswith("network search failed:")

    async def test_network_error(self):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("connection refused"),
        ):
            result = await _search_network("anything")
        assert result.startswith("network search failed:")

    async def test_untitled_fallback(self):
        resp = _mock_response(
            200,
            _semble_response(
                [
                    {"url": "https://example.com", "metadata": {}},
                ]
            ),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await _search_network("test")
        assert "untitled — https://example.com" in result
