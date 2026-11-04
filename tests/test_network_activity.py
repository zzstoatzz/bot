from types import SimpleNamespace

import httpx

from bot import main
from bot.config import settings


async def test_network_activity_delivery_retries_and_validation(monkeypatch, tmp_path):
    received = []

    async def receive(material):
        received.append(material)

    monkeypatch.setattr(settings, "control_token", "test-control")
    monkeypatch.setattr(main.bot_status, "last_network_activity_id", "")
    monkeypatch.setattr(main.bot_status, "paused", False)
    monkeypatch.setattr("bot.status.STATUS_FILE", tmp_path / "status.json")
    monkeypatch.setattr(
        main.app.state,
        "poller",
        SimpleNamespace(handler=SimpleNamespace(network_activity=receive)),
        raising=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        path = "/api/control/trigger/network-activity"
        event = {
            "event_id": "stream:1",
            "material": "892/s; typical 238/s; cause unknown",
        }
        assert (await client.post(path, json=event)).status_code == 401
        headers = {"authorization": "Bearer test-control"}
        assert (await client.post(path, headers=headers, json={})).status_code == 400
        assert (
            await client.post(path, headers=headers, json={"material": "x"})
        ).status_code == 400
        monkeypatch.setattr(main.bot_status, "paused", True)
        assert (await client.post(path, headers=headers, json=event)).status_code == 409
        assert received == []
        monkeypatch.setattr(main.bot_status, "paused", False)
        assert (await client.post(path, headers=headers, json=event)).status_code == 200
        reply = await client.post(path, headers=headers, json=event)
        assert reply.json()["duplicate"] is True
        assert received == [event["material"]]
        restored = type(main.bot_status)()
        restored._load()
        assert restored.last_network_activity_id == event["event_id"]
