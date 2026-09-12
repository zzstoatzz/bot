from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from atproto_client import models

from bot.core.atproto_client import BotClient
from bot.tools import bluesky


def view(uri, muted, root=None):
    post = models.AppBskyFeedDefs.PostView.model_construct(
        uri=uri,
        record=models.AppBskyFeedPost.Record.model_construct(
            reply=SimpleNamespace(root=SimpleNamespace(uri=root)) if root else None
        ),
        viewer=models.AppBskyFeedDefs.ViewerState(thread_muted=muted),
    )
    return SimpleNamespace(
        thread=models.AppBskyFeedDefs.ThreadViewPost.model_construct(post=post)
    )


def client(monkeypatch):
    bot = BotClient()
    monkeypatch.setattr(bot, "authenticate", AsyncMock())
    feed = SimpleNamespace(get_post_thread=Mock())
    bot.client = SimpleNamespace(
        app=SimpleNamespace(bsky=SimpleNamespace(feed=feed)), send_post=Mock()
    )
    return bot, feed


async def test_parent_resolves_root_and_reads_root_mute(monkeypatch):
    bot, feed = client(monkeypatch)
    feed.get_post_thread.side_effect = [
        view(
            "at://did:plc:test/app.bsky.feed.post/parent",
            False,
            "at://did:plc:test/app.bsky.feed.post/root",
        ),
        view("at://did:plc:test/app.bsky.feed.post/root", True),
    ]
    assert await bot.thread_mute_state(
        "at://did:plc:test/app.bsky.feed.post/parent"
    ) == ("at://did:plc:test/app.bsky.feed.post/root", True)
    assert (
        feed.get_post_thread.call_args.args[0]["uri"]
        == "at://did:plc:test/app.bsky.feed.post/root"
    )


@pytest.mark.parametrize("state", [True, None])
async def test_reply_refused_when_muted_or_unknown(monkeypatch, state):
    bot, feed = client(monkeypatch)
    feed.get_post_thread.return_value = view(
        "at://did:plc:test/app.bsky.feed.post/root", state
    )
    with pytest.raises(ValueError):
        await bot.create_post(
            "hello",
            reply_to=SimpleNamespace(
                root=SimpleNamespace(uri="at://did:plc:test/app.bsky.feed.post/root")
            ),
        )
    bot.client.send_post.assert_not_called()


async def test_mute_between_split_parts_stops_remaining_delivery(monkeypatch):
    bot, feed = client(monkeypatch)
    feed.get_post_thread.side_effect = [
        view("at://did:plc:test/app.bsky.feed.post/root", False),
        view("at://did:plc:test/app.bsky.feed.post/root", True),
    ]
    bot.client.send_post.return_value = SimpleNamespace(
        uri="at://did:plc:test/app.bsky.feed.post/first", cid="first"
    )
    ref = models.ComAtprotoRepoStrongRef.Main(
        uri="at://did:plc:test/app.bsky.feed.post/root",
        cid="at://did:plc:test/app.bsky.feed.post/root",
    )
    with pytest.raises(ValueError, match="muted"):
        await bot.create_post(
            "a " * 220, reply_to=models.AppBskyFeedPost.ReplyRef(root=ref, parent=ref)
        )
    assert bot.client.send_post.call_count == 1


@pytest.mark.parametrize(
    "action,initial,desired",
    [("add", False, True), ("add", True, True), ("remove", True, False)],
)
async def test_management_verifies_and_skips_redundant_write(
    monkeypatch, action, initial, desired
):
    tools = {}
    bluesky.register(SimpleNamespace(tool=lambda fn: tools.setdefault(fn.__name__, fn)))
    graph = SimpleNamespace(mute_thread=Mock(), unmute_thread=Mock())
    monkeypatch.setattr(
        bluesky.bot_client,
        "client",
        SimpleNamespace(app=SimpleNamespace(bsky=SimpleNamespace(graph=graph))),
    )
    monkeypatch.setattr(
        bluesky.bot_client,
        "thread_mute_state",
        AsyncMock(
            side_effect=[
                ("at://did:plc:test/app.bsky.feed.post/root", initial),
                ("at://did:plc:test/app.bsky.feed.post/root", desired),
            ]
        ),
    )
    result = await tools["manage_account"](
        None, "thread", action, "at://did:plc:test/app.bsky.feed.post/parent"
    )
    assert f"muted: {desired}" in result
    assert graph.mute_thread.call_count + graph.unmute_thread.call_count == int(
        initial != desired
    )


async def test_api_failure_stops_reply(monkeypatch):
    bot, feed = client(monkeypatch)
    feed.get_post_thread.side_effect = RuntimeError("service unavailable")
    with pytest.raises(RuntimeError, match="service unavailable"):
        await bot.create_post(
            "hello",
            reply_to=SimpleNamespace(
                root=SimpleNamespace(uri="at://did:plc:test/app.bsky.feed.post/root")
            ),
        )
    bot.client.send_post.assert_not_called()


async def test_unmuted_reply_delivers(monkeypatch):
    bot, feed = client(monkeypatch)
    feed.get_post_thread.return_value = view(
        "at://did:plc:test/app.bsky.feed.post/root", False
    )
    bot.client.send_post.return_value = SimpleNamespace(
        uri="at://did:plc:test/app.bsky.feed.post/sent"
    )
    await bot.create_post(
        "hello",
        reply_to=SimpleNamespace(
            root=SimpleNamespace(uri="at://did:plc:test/app.bsky.feed.post/root")
        ),
    )
    bot.client.send_post.assert_called_once()


async def test_new_root_retries_index_delay_without_resending(monkeypatch):
    bot, feed = client(monkeypatch)
    monkeypatch.setattr("bot.core.atproto_client.asyncio.sleep", AsyncMock())
    uri = "at://did:plc:test/app.bsky.feed.post/new"
    feed.get_post_thread.side_effect = [RuntimeError("NotFound"), view(uri, False)]
    bot.client.send_post.return_value = SimpleNamespace(uri=uri, cid="new")
    await bot.create_post("a " * 220)
    assert bot.client.send_post.call_count == 2
    assert feed.get_post_thread.call_count == 2


async def test_new_root_never_treats_missing_state_as_unmuted(monkeypatch):
    bot, feed = client(monkeypatch)
    sleep = AsyncMock()
    monkeypatch.setattr("bot.core.atproto_client.asyncio.sleep", sleep)
    feed.get_post_thread.side_effect = RuntimeError("NotFound")
    bot.client.send_post.return_value = SimpleNamespace(
        uri="at://did:plc:test/app.bsky.feed.post/new", cid="new"
    )
    with pytest.raises(ValueError, match="partial publication: 1"):
        await bot.create_post("a " * 220)
    assert bot.client.send_post.call_count == 1
    assert sleep.await_count == 4
