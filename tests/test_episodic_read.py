"""Exact note reads preserve evidence and distinguish missing from failed reads."""

import json
from types import SimpleNamespace

import httpx
import pytest
from turbopuffer import Turbopuffer

from bot.tools import memory as memory_tools


@pytest.mark.parametrize("stored_status", ["active", "superseded", None])
async def test_exact_reader_opens_version_without_rewriting_or_returning_vector(
    stored_status,
):
    text = "Only in that page.\n“Not exhaustive.”"
    row = {
        "id": "version-1",
        "content": text,
        "vector": [0.1],
        "source_uris": ["at://did:plc:example/app.bsky.feed.post/abc"],
        "supersedes": "version-0",
        "created_at": "2026-09-05T12:00:00Z",
    }
    if stored_status:
        row["status"] = stored_status
    calls = []

    def serve(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"rows": [row]})

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        tools = {}
        memory_tools.register(
            SimpleNamespace(tool=lambda fn: tools.setdefault(fn.__name__, fn))
        )
        ctx = SimpleNamespace(
            deps=SimpleNamespace(
                memory=SimpleNamespace(
                    namespaces={"episodic": client.namespace("notes")}
                )
            )
        )
        result = json.loads(await tools["read_memory"](ctx, "version-1"))
    assert len(calls) == 1
    assert calls[0]["filters"] == ["id", "Eq", "version-1"]
    assert result["status"] == "ok"
    assert result["note"]["content"] == text
    assert result["note"]["status"] == stored_status
    assert result["note"]["supersedes"] == "version-0"
    assert result["note"]["source_uris"] == row["source_uris"]
    assert "vector" not in result["note"]


@pytest.mark.parametrize(
    "code,expected",
    [(200, "not_found"), (404, "namespace_missing"), (503, "unavailable")],
)
async def test_absence_and_backend_failure_are_distinct(code, expected):
    def serve(request):
        return httpx.Response(
            code, json={"rows": []} if code == 200 else {"error": "offline"}
        )

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        tools = {}
        memory_tools.register(
            SimpleNamespace(tool=lambda fn: tools.setdefault(fn.__name__, fn))
        )
        ctx = SimpleNamespace(
            deps=SimpleNamespace(
                memory=SimpleNamespace(
                    namespaces={"episodic": client.namespace("notes")}
                )
            )
        )
        result = json.loads(await tools["read_memory"](ctx, "missing-version"))
    assert result == {"status": expected, "note": None}
