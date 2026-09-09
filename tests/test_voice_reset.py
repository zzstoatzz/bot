"""Normal entry points cannot assemble context during the voice reset."""

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


def test_reset_rejects_external_runs_and_resume(monkeypatch):
    monkeypatch.setattr(settings, "voice_reset", True)
    monkeypatch.setattr(settings, "control_token", "test-reset-token")
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-reset-token"}
    for endpoint in ["/api/control/resume", "/api/control/trigger/cycle"]:
        response = client.post(endpoint, headers=headers)
        assert response.status_code == 409
        assert response.json() == {"error": "voice reset is active"}
