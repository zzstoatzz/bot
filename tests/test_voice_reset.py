"""Normal entry points cannot assemble context during the voice reset."""

from unittest.mock import AsyncMock, Mock

from starlette.testclient import TestClient

from bot.agent import PhiAgent
from bot.config import settings
from bot.main import app


async def test_reset_prevents_context_tools_and_extraction(monkeypatch):
    monkeypatch.setattr(settings, "voice_reset", True)
    agent = PhiAgent.__new__(PhiAgent)
    assert await agent._run_agent(label="test", prompt="test", deps=None) == (
        "normal runs suspended for voice reset"
    )
    assert await agent.process_extraction() == 0
    assert await agent.render_context_preview() == []
    assert await agent.list_tool_definitions() == []


def test_reset_rejects_external_runs_and_resume(monkeypatch):
    monkeypatch.setattr(settings, "voice_reset", True)
    monkeypatch.setattr(settings, "control_token", "test-reset-token")
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-reset-token"}
    for endpoint in ["/api/control/resume", "/api/control/trigger/cycle"]:
        response = client.post(endpoint, headers=headers)
        assert response.status_code == 409
        assert response.json() == {"error": "voice reset is active"}


async def test_reset_budget_has_no_context_or_provider_probe(monkeypatch):
    monkeypatch.setattr(settings, "voice_reset", True)
    limits = Mock()
    limits.as_dict.return_value = {"name": "test-model"}
    monkeypatch.setattr(
        "bot.core.model_catalog.lookup_model_limits", AsyncMock(return_value=limits)
    )
    agent = PhiAgent.__new__(PhiAgent)
    counter = AsyncMock(side_effect=AssertionError("provider must not be called"))
    agent.agent = Mock(model=Mock(count_tokens=counter))

    budget = await agent.render_context_budget()

    assert budget["voice_reset"] is True
    assert budget["sections"] == []
    assert budget["totals"] == {"static": 0, "blocks": 0, "tools": 0, "prompt": 0}
    counter.assert_not_awaited()
