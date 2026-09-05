"""The cockpit must expose evidence behind an exchange count."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import bot.main as main


@pytest.mark.parametrize("mode", ["linked", "legacy", "empty", "unavailable"])
async def test_user_view_exchange_evidence(monkeypatch, mode):
    references = [
        "at://did:plc:alice/app.bsky.feed.post/question",
        "at://did:plc:phi/app.bsky.feed.post/reply",
    ]
    rows = [
        SimpleNamespace(
            id=f"exchange-{i}",
            kind="interaction",
            content=f"user: question {i}\nbot: answer {i}",
            created_at=f"2026-09-0{7 - i}T00:00:00",
            **({"source_uris": references} if mode == "linked" else {}),
        )
        for i in range(7)
    ]
    namespace = Mock()

    def query(*, filters=None, include_attributes, **kwargs):
        if filters == {"kind": ["Eq", "interaction"]}:
            if mode == "unavailable":
                raise RuntimeError("storage unavailable")
            assert include_attributes is True
            assert kwargs["rank_by"] == ("created_at", "desc")
            return SimpleNamespace(rows=[] if mode == "empty" else rows)
        return SimpleNamespace(rows=[])

    namespace.query.side_effect = query
    memory = Mock()
    memory.get_user_namespace.return_value = namespace
    memory.is_stranger = AsyncMock(return_value=True)
    poller = SimpleNamespace(handler=SimpleNamespace(agent=SimpleNamespace(memory=memory)))
    monkeypatch.setattr(main.app.state, "poller", poller, raising=False)
    monkeypatch.setattr(main, "_user_view_cache", {})
    monkeypatch.setattr(main.bot_client, "authenticate", AsyncMock())
    sdk = Mock()
    sdk.app.bsky.actor.get_profile.return_value = SimpleNamespace(did="did:plc:alice")
    monkeypatch.setattr(main.bot_client, "client", sdk)

    response = await main.user_view("alice.test")
    body = json.loads(response.body)
    exchanges = body["recent_interactions"]
    if mode == "unavailable":
        assert exchanges is None
    elif mode == "empty":
        assert exchanges == []
    else:
        assert body["counts"]["interaction"] == 7
        assert len(exchanges) == 5
        assert exchanges[0]["content"] == "user: question 0\nbot: answer 0"
        assert exchanges[0]["source_uris"] == (references if mode == "linked" else [])
        assert exchanges[0]["created_at"] == "2026-09-07T00:00:00"
