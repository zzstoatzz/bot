"""Run summaries and swallowed model failures cannot fabricate completed receipts."""

import asyncio
import json
from unittest.mock import Mock

import httpx
import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from turbopuffer import Turbopuffer

from bot.agent import PhiAgent
from bot.core.cache_stability import CacheObservingModel
from bot.memory.namespace_memory import NamespaceMemory
from bot.memory.run_evidence import current_run
from bot.tools._helpers import PhiDeps


@pytest.mark.parametrize("outcome", ["success", "failure", "cancelled"])
async def test_model_boundary_and_run_outcome_remain_distinct(outcome, monkeypatch):
    stored = {}
    writes = []

    def serve(request):
        body = json.loads(request.content)
        writes.extend(body["upsert_rows"])
        for row in body["upsert_rows"]:
            stored[row["id"]] = row
        return httpx.Response(200, json={"rows_affected": len(body["upsert_rows"])})

    async def respond(messages, info):
        assert any(r["status"] == "prepared" for r in stored.values())
        if outcome == "failure":
            raise RuntimeError("model unavailable")
        if outcome == "cancelled":
            raise asyncio.CancelledError()
        return ModelResponse(parts=[TextPart("no public action taken")])

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as storage:
        phi = PhiAgent.__new__(PhiAgent)
        phi._mcp_toolsets = lambda **kwargs: []
        phi.agent = Agent(
            model=CacheObservingModel(FunctionModel(respond), monitor=Mock())
        )

        @phi.agent.instructions
        def inject_event():
            run = current_run.get()
            assert run is not None
            run.event_ids.add("captured-event")
            return "[RECENT ENCOUNTERS] original incoming event"

        monkeypatch.setattr("bot.agent.cache_monitor", Mock())
        memory = NamespaceMemory.__new__(NamespaceMemory)
        memory.client = storage
        deps = PhiDeps(author_handle="", memory=memory)
        if outcome == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await phi._run_agent(label="bio rewrite", prompt="test", deps=deps)
        else:
            await phi._run_agent(label="bio rewrite", prompt="test", deps=deps)
    assert current_run.get() is None
    request = next(r for r in stored.values() if r["kind"] == "model_request")
    assert request["event_ids"] == ["captured-event"]
    assert request["instruction_chars"] > 0
    assert len(request["instruction_sha256"]) == 64
    statuses = {r["status"] for r in stored.values() if r["kind"] == "run_status"}
    if outcome == "success":
        assert request["status"] == "response_received"
        assert statuses == {"started", "completed"}
    else:
        assert request["status"] == "failed_or_interrupted"
        assert "completed" not in statuses
        assert ("failed" in statuses) == (outcome == "failure")
    assert all("action" not in r for r in writes)
