"""Exercise the registered identity tool against an HTTP transport."""

import json
from types import SimpleNamespace

import httpx
import pytest

from bot.tools import search


def tool_with_transport(monkeypatch, handler):
    constructor = httpx.AsyncClient
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
    return tools["search_people"]


async def test_ambiguous_name_retains_both_candidates(monkeypatch):
    def handler(request):
        assert request.url.host == "typeahead.waow.tech"
        assert request.url.path == "/xrpc/tech.waow.typeahead.searchActors"
        assert request.url.params["q"] == "Ali"
        assert request.url.params["limit"] == "10"
        assert request.headers["X-Client"] == "phi.zzstoatzz.io"
        return httpx.Response(
            200,
            json={
                "actors": [
                    {"did": "did:plc:a", "handle": "a.test", "displayName": "Ali"},
                    {"did": "did:plc:b", "handle": "b.test", "displayName": "Ali"},
                ]
            },
        )

    tool = tool_with_transport(monkeypatch, handler)
    result = json.loads(await tool(None, " @Ali "))
    assert [a["did"] for a in result["candidates"]] == ["did:plc:a", "did:plc:b"]
    assert "selected" not in result


@pytest.mark.parametrize("status,payload", [(503, {}), (200, {"oops": []})])
async def test_failure_is_not_no_matching_account(monkeypatch, status, payload):
    tool = tool_with_transport(
        monkeypatch, lambda request: httpx.Response(status, json=payload)
    )
    assert "unavailable" in await tool(None, "Ali")


async def test_empty_results_are_successful_lookup(monkeypatch):
    tool = tool_with_transport(
        monkeypatch, lambda request: httpx.Response(200, json={"actors": []})
    )
    assert json.loads(await tool(None, "unknown")) == {"candidates": []}


async def test_blank_query_never_calls_service(monkeypatch):
    def handler(request):
        pytest.fail("blank query should not call the service")

    tool = tool_with_transport(monkeypatch, handler)
    assert "Provide a name" in await tool(None, " @ ")
