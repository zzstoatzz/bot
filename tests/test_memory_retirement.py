"""Retirement removes recall eligibility, not source evidence."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from turbopuffer import Turbopuffer

from bot.memory.namespace_memory import NamespaceMemory
from bot.tools import memory as memory_tools


async def test_retire_read_restore_and_search_paths():
    rows = {
        "chosen": {
            "id": "chosen",
            "content": "old obligation",
            "status": "active",
            "source_uris": ["at://source"],
            "$dist": 0.1,
        },
        "other": {"id": "other", "content": "interesting project", "$dist": 0.2},
    }
    writes = []

    def serve(request):
        data = json.loads(request.content)
        if "patch_rows" in data:
            writes.append(data)
            for row in data["patch_rows"]:
                rows[row["id"]].update(row)
            return httpx.Response(200, json={})
        if data.get("filters", [None])[0] == "id":
            row = rows.get(data["filters"][2])
            return httpx.Response(200, json={"rows": [row] if row else []})
        return httpx.Response(200, json={"rows": list(rows.values())})

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        mem = NamespaceMemory.__new__(NamespaceMemory)
        mem.namespaces = {"episodic": client.namespace("notes")}
        mem._get_embedding = AsyncMock(return_value=[0.1])
        mem.get_user_namespace = lambda _: client.namespace("unused")
        tools = {}
        memory_tools.register(
            SimpleNamespace(tool=lambda fn: tools.setdefault(fn.__name__, fn))
        )
        ctx = SimpleNamespace(deps=SimpleNamespace(memory=mem, run_cache={}))
        assert "Read this note" in await tools["retire_memory"](
            ctx, "chosen", "no longer useful"
        )
        assert not writes
        await tools["read_memory"](ctx, "chosen")
        result = json.loads(
            await tools["retire_memory"](ctx, "chosen", "no longer useful")
        )
        assert result["note"]["status"] == "retired"
        assert result["note"]["content"] == "old obligation"
        assert result["note"]["source_uris"] == ["at://source"]
        assert result["note"]["retired_reason"] == "no longer useful"
        for found in [
            await mem.search_episodic("old"),
            await mem.search_unified("", "old"),
            await mem._find_similar_episodic([0.1]),
        ]:
            assert [r["id"] for r in found] == ["other"]
        exact = json.loads(await tools["read_memory"](ctx, "chosen"))
        assert exact["note"]["content"] == "old obligation"
        await tools["restore_memory"](ctx, "chosen")
        assert {r["id"] for r in await mem.search_episodic("old")} == {
            "chosen",
            "other",
        }
        rows["chosen"]["status"] = "superseded"
        with pytest.raises(ValueError, match="Superseded"):
            await mem.set_memory_retired("chosen", False)
        assert len(writes) == 2
