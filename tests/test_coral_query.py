"""Exercise the graph tool with payloads that previously became broken JSON."""

import json
from types import SimpleNamespace

import httpx
import pytest

from bot.tools import search


def graph_tool(monkeypatch, payload):
    constructor = httpx.AsyncClient

    def handler(request):
        assert request.url.path in {"/entity-graph", "/simcluster/entity-graph"}
        assert not request.url.query
        return httpx.Response(200, json=payload)

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
    return tools["coral_query"]


async def test_oversized_graph_pages_preserve_every_entity(monkeypatch):
    entities = [
        {
            "id": i,
            "text": f"Entity {i:04}",
            "label": "PERSON",
            "surprise": i / 10,
            "edges": [{"t": j, "w": 1.5} for j in range(100)],
        }
        for i in range(100)
    ]
    payload = {"entities": entities}
    assert len(json.dumps(payload)) > 183288
    tool = graph_tool(monkeypatch, payload)
    found = []
    offset = 0
    while offset is not None:
        body = await tool(None, "/entity-graph", offset=offset)
        assert len(body) < 8000
        page = json.loads(body)
        assert page["total_entities"] == page["matching_entities"] == 100
        assert page["returned"] == 20
        for entity in page["entities"]:
            assert entity["edge_count"] == 100
            assert entity["surprise"] == entity["id"] / 10
        found.extend(e["id"] for e in page["entities"])
        offset = page["next_offset"]
    assert found == list(range(100))


async def test_search_reaches_late_entities_and_cohort(monkeypatch):
    tool = graph_tool(
        monkeypatch,
        {
            "entities": [
                {"id": 1, "text": "Alpha"},
                {"id": 2, "text": "Drew"},
                {"id": 3, "text": "Drew Rasmussen"},
                {"id": 4, "text": "東京"},
            ]
        },
    )
    page = json.loads(
        await tool(None, "/simcluster/entity-graph", query=" DREW ", limit=1)
    )
    assert page["matching_entities"] == 2
    assert page["next_offset"] == 1
    page = json.loads(
        await tool(None, "/simcluster/entity-graph", query="drew", limit=1, offset=1)
    )
    assert page["entities"][0]["text"] == "Drew Rasmussen"
    assert page["next_offset"] is None
    empty = json.loads(await tool(None, "/entity-graph", query="absent"))
    assert empty["entities"] == [] and empty["next_offset"] is None


async def test_unsupported_graph_url_parameters_are_explicit(monkeypatch):
    tool = graph_tool(monkeypatch, {})
    assert "remove URL parameters" in await tool(None, "/entity-graph?limit=10")


@pytest.mark.parametrize("payload", [{}, {"entities": [None]}, {"entities": [{}]}])
async def test_malformed_graph_is_failure_not_empty_page(monkeypatch, payload):
    tool = graph_tool(monkeypatch, payload)
    assert "failed" in await tool(None, "/entity-graph")
