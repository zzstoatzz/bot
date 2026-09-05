"""A user refresh bypasses the short cache and surfaces upstream failure."""

import json
import time
from unittest.mock import AsyncMock, patch

import httpx

import bot.main as main


async def test_refresh_fetches_upstream_even_with_a_warm_cache():
    cached = {"value": "old"}
    response = httpx.Response(
        200, json={"value": "new"}, request=httpx.Request("GET", "https://example.test")
    )
    upstream = AsyncMock()
    upstream.get.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = upstream
    with (
        patch.dict(
            main._chicken_cache, {"market": (time.monotonic() + 60, cached)}, clear=True
        ),
        patch("bot.main.httpx.AsyncClient", return_value=context),
    ):
        normal = await main.chicken("market")
        assert json.loads(normal.body) == cached
        upstream.get.assert_not_called()
        fresh = await main.chicken("market", refresh=True)
        assert json.loads(fresh.body) == {"value": "new"}
        assert fresh.headers["cache-control"] == "no-store"
        assert upstream.get.await_count == 1


async def test_refresh_failure_does_not_present_cache_as_a_success():
    upstream = AsyncMock()
    upstream.get.side_effect = httpx.ConnectError("offline")
    context = AsyncMock()
    context.__aenter__.return_value = upstream
    with (
        patch.dict(
            main._chicken_cache,
            {"market": (time.monotonic() + 60, {"old": True})},
            clear=True,
        ),
        patch("bot.main.httpx.AsyncClient", return_value=context),
    ):
        response = await main.chicken("market", refresh=True)
        assert response.status_code == 502
