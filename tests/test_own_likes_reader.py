"""The raw-search fix must not remove Phi's existing bookmark reader."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bot.core.atproto_client import BotClient
from bot.tools import bluesky


async def test_registered_likes_tool_reads_authenticated_accounts_bookmarks(
    monkeypatch,
):
    client = BotClient.__new__(BotClient)
    monkeypatch.setattr(client, "authenticate", AsyncMock())
    sdk = Mock()
    sdk.me.did = "did:plc:phi"
    post = SimpleNamespace(
        uri="at://did:plc:ali/app.bsky.feed.post/reply",
        author=SimpleNamespace(handle="ali.test"),
        record=SimpleNamespace(text="the reply Phi liked without answering"),
        indexed_at="2026-09-05T02:46:24Z",
    )
    sdk.app.bsky.feed.get_actor_likes.return_value = SimpleNamespace(
        feed=[SimpleNamespace(post=post)]
    )
    monkeypatch.setattr(client, "client", sdk, raising=False)
    monkeypatch.setattr(bluesky, "bot_client", client)
    registered = {}

    def register(tool):
        registered[tool.__name__] = tool
        return tool

    bluesky.register(SimpleNamespace(tool=register))
    result = await registered["get_own_likes"](SimpleNamespace(), limit=7)
    client.authenticate.assert_awaited_once()
    sdk.app.bsky.feed.get_actor_likes.assert_called_once_with(
        params={"actor": "did:plc:phi", "limit": 7}
    )
    assert post.uri in result
    assert "@ali.test" in result
    assert post.record.text in result


async def test_raw_search_keeps_unknown_embed_types(monkeypatch):
    client = BotClient.__new__(BotClient)
    monkeypatch.setattr(client, "authenticate", AsyncMock())
    payload = {"posts": [{"embed": {"$type": "example.future.embed#view"}}]}
    sdk = Mock()
    sdk.invoke_query.return_value = SimpleNamespace(content=payload)
    monkeypatch.setattr(client, "client", sdk, raising=False)
    result = await client.search_posts_raw({"q": "ten votes", "limit": 7})
    assert result == payload
    sent = sdk.invoke_query.call_args.kwargs
    assert sent["params"].q == "ten votes"
    assert sent["params"].limit == 7
    assert sent["output_encoding"] == "application/json"
