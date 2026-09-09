from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr

from bot.tools import workflows


@pytest.fixture
def harness(monkeypatch):
    registered = {}

    def tool(fn):
        registered[fn.__name__] = fn
        return fn

    workflows.register(SimpleNamespace(tool=tool))
    monkeypatch.setattr(workflows, "_is_owner", lambda ctx: True)
    monkeypatch.setattr(
        workflows, "get_override", AsyncMock(return_value={"active": False})
    )
    monkeypatch.setattr(
        workflows.settings, "prefect_api_auth_string", "readonly:unused"
    )
    monkeypatch.setattr(
        workflows.settings, "workflow_request_token", SecretStr("request-test-token")
    )
    requests = []
    pool = {"name": "phi-sprites-spike"}

    def handle(request):
        requests.append(request)
        if pool["name"] != "phi-sprites-spike":
            return httpx.Response(400)
        return httpx.Response(200, json={"flow_run_id": "run-id", "name": "test-run"})

    client = httpx.AsyncClient
    monkeypatch.setattr(
        workflows.httpx,
        "AsyncClient",
        lambda **kw: client(transport=httpx.MockTransport(handle), **kw),
    )
    return registered["request_workflow"], requests, pool


async def test_investigation_queues_fixed_capabilities_and_stable_retry(harness):
    import json

    request, calls, _ = harness
    kwargs = {
        "workflow": "investigate",
        "instructions": "Explain the failure",
        "repo": "bot",
        "request_key": "at://request/one",
    }
    result = await request(None, **kwargs)
    assert result["flow_run_id"] == "run-id"
    first = json.loads(calls[-1].content)
    assert first["workflow"] == "investigate"
    await request(None, **kwargs)
    assert json.loads(calls[-1].content)["request_key"] == first["request_key"]


async def test_old_home_deployment_is_not_silently_used(harness):
    request, calls, pool = harness
    pool["name"] = "home-pool"
    result = await request(
        None,
        workflow="investigate",
        instructions="Explain",
        repo="bot",
        request_key="one",
    )
    assert result["queued"] is False
    assert [c.method for c in calls] == ["POST"]


async def test_nonowner_cannot_queue(harness, monkeypatch):
    request, calls, _ = harness
    monkeypatch.setattr(workflows, "_is_owner", lambda ctx: False)
    assert not (
        await request(
            None,
            workflow="investigate",
            instructions="Explain",
            repo="bot",
            request_key="one",
        )
    )["queued"]
    assert calls == []


async def test_proposal_preserves_phi_as_requester(harness):
    import json

    request, calls, _ = harness
    await request(
        None,
        workflow="propose-change",
        instructions="Fix it",
        repo="bot",
        request_key="one",
        title="Fix",
        body="Acceptance criteria",
    )
    payload = json.loads(calls[-1].content)
    assert payload["workflow"] == "propose-change"
    assert calls[-1].headers["Authorization"] == "Bearer request-test-token"
    assert "agent" not in payload
    assert "job_variables" not in payload


async def test_override_blocks_request(harness, monkeypatch):
    request, calls, _ = harness
    monkeypatch.setattr(
        workflows,
        "get_override",
        AsyncMock(return_value={"active": True, "message": "paused"}),
    )
    assert not (
        await request(
            None,
            workflow="investigate",
            instructions="Explain",
            repo="bot",
            request_key="one",
        )
    )["queued"]
    assert calls == []
