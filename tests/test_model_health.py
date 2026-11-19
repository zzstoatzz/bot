"""/health reports a model whose provider refuses its account.

2026-11-14 and 2026-11-19: OpenRouter, then OpenAI, ran out of credits.
Every run failed at its first model call while the poller kept ticking, so
/health and the site said phi was online. A restart cannot pay a bill, so
this is a 200 `degraded`, not a 503 that the watchdog would restart.
"""

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelQuotaExceededError, ModelRateLimitError
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from starlette.testclient import TestClient

import bot.main as m
from bot.config import settings
from bot.core import model_health, watchdog
from bot.core.model_health import checked
from bot.status import bot_status


@pytest.fixture(autouse=True)
def clean():
    model_health.reset()
    yield
    model_health.reset()


def scripted(*outcomes):
    """A model that raises or answers in turn."""
    queue = list(outcomes)

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return ModelResponse(parts=[TextPart(outcome)])

    return FunctionModel(respond, model_name="judge")


def quota() -> ModelQuotaExceededError:
    return ModelQuotaExceededError("judge", "402: requires more credits")


async def test_an_account_failure_marks_the_model_until_it_answers():
    agent = Agent(checked(scripted(quota(), "ok")))
    with pytest.raises(ModelQuotaExceededError):
        await agent.run("hi")
    [down] = model_health.unavailable()
    assert down.model == "judge" and down.reason.startswith("out of credits")

    await agent.run("hi again")
    assert model_health.unavailable() == []


async def test_a_rate_limit_is_not_an_account_failure():
    agent = Agent(checked(scripted(ModelRateLimitError("judge", "429"))))
    with pytest.raises(ModelRateLimitError):
        await agent.run("hi")
    assert model_health.unavailable() == []


def test_health_is_degraded_but_200_and_the_watchdog_keeps_the_process():
    bot_status.polling_active = True
    bot_status.paused = False
    bot_status.record_tick()
    model_health.record_failure("deepseek/deepseek-v4.1-flash", quota())

    r = TestClient(m.app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert "deepseek/deepseek-v4.1-flash: out of credits" in body["reason"]
    assert body["models_unavailable"][0]["model"] == "deepseek/deepseek-v4.1-flash"
    assert watchdog.stale_reason(bot_status, settings.health_stale_after) is None
