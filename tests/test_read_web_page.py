"""Source reading returns complete, pageable evidence and explicit failures."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from bot.tools import search


def reader(monkeypatch, handler):
    constructor = httpx.AsyncClient
    monkeypatch.setattr(search.settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(
        search.httpx,
        "AsyncClient",
        lambda **kwargs: constructor(transport=httpx.MockTransport(handler), **kwargs),
    )
    tools = {}

    def register(tool):
        tools[tool.__name__] = tool
        return tool

    search.register(SimpleNamespace(tool=register))
    return tools["read_web_page"]


async def test_read_all_pages_without_loss(monkeypatch):
    content = "é🦎 source material\n" * 1400

    def handler(request):
        assert request.url == "https://api.tavily.com/extract"
        body = json.loads(request.content)
        assert body == {
            "urls": ["https://example.org/story"],
            "format": "markdown",
            "extract_depth": "basic",
        }
        return httpx.Response(200, json={"results": [{"raw_content": content}]})

    tool = reader(monkeypatch, handler)
    parts = []
    offset = 0
    while offset is not None:
        page = json.loads(await tool(None, "https://example.org/story", offset))
        assert page["offset"] == offset
        assert page["total_chars"] == len(content)
        assert len(page["content"]) <= 12_000
        parts.append(page["content"])
        offset = page["next_offset"]
    assert "".join(parts) == content


@pytest.mark.parametrize(
    "status,payload",
    [
        (401, {}),
        (503, {}),
        (200, {"results": []}),
        (200, {"results": [{"raw_content": ""}]}),
        (200, {"results": [{"raw_content": None}]}),
    ],
)
async def test_failure_is_not_source_absence(monkeypatch, status, payload):
    tool = reader(monkeypatch, lambda r: httpx.Response(status, json=payload))
    assert "unavailable" in await tool(None, "https://example.org/story")


@pytest.mark.parametrize(
    "url,offset", [("file:///etc/passwd", 0), ("https://example.org", -1)]
)
async def test_invalid_request_does_not_fetch(monkeypatch, url, offset):
    def handler(request):
        pytest.fail("invalid input must not fetch")

    tool = reader(monkeypatch, handler)
    assert "Provide" in await tool(None, url, offset)


async def test_bluesky_uses_native_reader_without_tavily(monkeypatch):
    def handler(request):
        pytest.fail("Bluesky post must not reach HTML extraction")

    tool = reader(monkeypatch, handler)
    monkeypatch.setattr(search.settings, "tavily_api_key", "")
    native = AsyncMock(return_value=["native evidence"])
    monkeypatch.setattr(search, "read_post_url", native)
    url = "https://bsky.app/profile/gracekind.net/post/3lktq6zw5ec2y"
    assert await tool(None, url) == ["native evidence"]
    native.assert_awaited_once_with(
        url, "at://gracekind.net/app.bsky.feed.post/3lktq6zw5ec2y"
    )
