import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from bot import status
from bot.agent import PhiAgent
from bot.services import notification_poller as module
from bot.services.message_handler import MessageHandler
from bot.services.notification_poller import NotificationPoller
from bot.tools import PhiDeps, media


async def test_bio_refresh_is_background_recurring_and_never_overlaps(monkeypatch):
    poller = object.__new__(NotificationPoller)
    poller._bio_task = None
    poller._next_bio_refresh = 0
    poller._background_tasks = set()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def work():
        calls.append(True)
        started.set()
        await release.wait()

    monkeypatch.setattr(poller, "_refresh_bio", work)
    monkeypatch.setattr(module.bot_status, "paused", False)
    monkeypatch.setattr(module.settings, "voice_reset", False)
    poller._schedule_bio_refresh()
    await asyncio.wait_for(started.wait(), 1)
    first = poller._bio_task
    assert first is not None and not first.done()
    poller._schedule_bio_refresh()
    assert poller._bio_task is first
    poller._next_bio_refresh = 0
    poller._schedule_bio_refresh()
    assert poller._bio_task is first
    release.set()
    await first
    poller._schedule_bio_refresh()
    assert poller._bio_task is not None
    await poller._bio_task
    assert len(calls) == 2


async def test_paused_bio_refresh_stays_due_until_resume(monkeypatch):
    poller = object.__new__(NotificationPoller)
    poller._bio_task = None
    poller._next_bio_refresh = 0
    monkeypatch.setattr(module.bot_status, "paused", True)
    poller._schedule_bio_refresh()
    assert poller._bio_task is None
    assert poller._next_bio_refresh == 0


async def test_weekly_review_survives_restart_and_daily_bios_continue(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(status, "STATUS_FILE", tmp_path / "status.json")
    state = status.BotStatus()
    monkeypatch.setattr(module, "bot_status", state)
    monkeypatch.setattr(module.settings, "voice_reset", False)

    async def override():
        return {"active": False}

    monkeypatch.setattr(module, "get_override", override)
    reviews = []

    async def process_bio(*, review_images):
        reviews.append(review_images)
        return "Kept the images; refreshed the bio."

    poller = object.__new__(NotificationPoller)
    poller._semaphore = asyncio.Semaphore(1)
    poller.handler = MessageHandler.__new__(MessageHandler)
    poller.handler.agent = PhiAgent.__new__(PhiAgent)
    monkeypatch.setattr(poller.handler.agent, "process_bio", process_bio)
    await poller._refresh_bio()
    assert state.last_profile_review_at is not None

    restored = status.BotStatus()
    restored._load()
    assert restored.last_profile_review_at == state.last_profile_review_at
    monkeypatch.setattr(module, "bot_status", restored)
    await poller._refresh_bio()
    restored.last_profile_review_at = datetime.now(UTC) - timedelta(days=7)
    await poller._refresh_bio()
    assert reviews == [True, False, True]


@pytest.mark.parametrize("outcome", ["failed", "timeout", "paused", "override"])
async def test_unsuccessful_review_stays_due(monkeypatch, tmp_path, outcome):
    monkeypatch.setattr(status, "STATUS_FILE", tmp_path / "status.json")
    state = status.BotStatus(paused=outcome == "paused")
    monkeypatch.setattr(module, "bot_status", state)
    monkeypatch.setattr(module.settings, "voice_reset", False)

    async def override():
        return {"active": outcome == "override"}

    async def process_bio(*, review_images):
        assert outcome not in {"paused", "override"}
        if outcome == "timeout":
            raise TimeoutError
        return "bio rewrite failed: provider unavailable"

    monkeypatch.setattr(module, "get_override", override)
    poller = object.__new__(NotificationPoller)
    poller._semaphore = asyncio.Semaphore(1)
    poller.handler = MessageHandler.__new__(MessageHandler)
    poller.handler.agent = PhiAgent.__new__(PhiAgent)
    monkeypatch.setattr(poller.handler.agent, "process_bio", process_bio)
    await poller._refresh_bio()
    restored = status.BotStatus()
    restored._load()
    assert state.last_profile_review_at is restored.last_profile_review_at is None


async def test_weekly_review_uses_the_same_agent_context_and_tools_as_mentions(
    monkeypatch,
):
    requests = []
    context = {"self": "I read and draw."}

    async def respond(messages, info):
        requests.append((messages, info))
        return ModelResponse(parts=[TextPart("Kept the profile images.")])

    phi = PhiAgent.__new__(PhiAgent)
    phi.memory = None
    phi.agent = Agent(FunctionModel(respond), deps_type=PhiDeps)
    media.register(phi.agent)

    @phi.agent.instructions
    def current_self():
        return context["self"]

    monkeypatch.setattr(phi, "_mcp_toolsets", lambda **kwargs: [])
    monkeypatch.setattr(module.settings, "voice_reset", False)
    await phi.process_notifications(
        {"at://test/post/1": {"author_handle": "nate", "post_text": "hello"}}
    )
    context["self"] = "I read, draw, and have changed since the last run."
    await phi.process_bio(review_images=True)

    (_, mention), (messages, weekly) = requests
    assert mention.instructions == "I read and draw."
    assert weekly.instructions == context["self"]
    assert (
        [t.name for t in weekly.function_tools]
        == [t.name for t in mention.function_tools]
        == ["inspect_record_media"]
    )
    assert "inspect_record_media" in str(messages)
