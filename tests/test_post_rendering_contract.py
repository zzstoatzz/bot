"""Every surface that shows phi a post shows its address and its replies.

Posts were rendered seven ways, and most dropped the at-uri or the reply
count. Phi saw posts she couldn't open and couldn't tell anyone had answered
(she asked bufo.uk what jev said instead of reading jev's reply, 2026-10-20).
Each surface below is built from the same fixture posts; a line that shows a
post's text must carry its uri, and its reply count when it has replies.
"""

from datetime import date
from types import SimpleNamespace
from typing import cast

import pytest

from bot.core import discovery_pool
from bot.core.atproto_client import BotClient
from bot.tools._helpers import _format_feed_posts
from bot.tools.search import render_posts
from bot.utils.lookup import fetch_author_lookup
from bot.utils.thread import fetch_thread_context, render_thread

POSTS = [
    ("at://did:plc:a/app.bsky.feed.post/1", "a.test", "top 10 movies all time?", 2),
    ("at://did:plc:b/app.bsky.feed.post/2", "b.test", "depends on taste", 1),
    ("at://did:plc:c/app.bsky.feed.post/3", "c.test", "anything by wong kar-wai", 0),
]


def _view(uri, handle, text, replies):
    return SimpleNamespace(
        uri=uri,
        author=SimpleNamespace(handle=handle),
        record=SimpleNamespace(text=text),
        reply_count=replies,
        quote_count=0,
        like_count=3,
        indexed_at="2026-10-20T07:13:40Z",
        embed=None,
    )


def _json(uri, handle, text, replies):
    return {
        "uri": uri,
        "author": {"handle": handle},
        "record": {"text": text},
        "replyCount": replies,
        "likeCount": 3,
        "indexedAt": "2026-10-20T07:13:40Z",
    }


def _chain(make):
    """Each fixture post replies to the one before."""
    node = None
    for post in reversed(POSTS):
        node = {"post": make(*post), "replies": [node] if node else []}
    return node if make is _json else _ns(node)


def _ns(node):
    return SimpleNamespace(
        post=node["post"], parent=None, replies=[_ns(r) for r in node["replies"]]
    )


async def _lookup_block():
    async def authenticate():
        return None

    feed = [SimpleNamespace(post=_view(*p)) for p in POSTS]
    bsky = SimpleNamespace(
        actor=SimpleNamespace(
            get_profile=lambda params: SimpleNamespace(description="hi")
        ),
        feed=SimpleNamespace(get_author_feed=lambda params: SimpleNamespace(feed=feed)),
    )
    client = SimpleNamespace(
        authenticate=authenticate,
        client=SimpleNamespace(app=SimpleNamespace(bsky=bsky)),
    )
    return await fetch_author_lookup(cast(BotClient, client), "a.test")


def _discovery_block():
    entries: list[discovery_pool._Entry] = [
        {
            "handle": handle,
            "did": "did:plc:x",
            "likes_in_window": 1,
            "last_liked_at": "",
            "sample_posts": [{"uri": uri, "text": text, "liked_at": ""}],
        }
        for uri, handle, text, _ in POSTS
    ]
    views = {p[0]: _json(*p) for p in POSTS}
    return discovery_pool._render(entries, ranked=False, samples=1, views=views)


SURFACES = {
    "thread (atproto views)": lambda: render_thread(_chain(_view)),
    "thread (appview json)": lambda: render_thread(_chain(_json)),
    "search_posts": lambda: render_posts(
        [_json(*p) for p in POSTS], date(2026, 10, 20)
    ),
    "feeds": lambda: _format_feed_posts(
        [SimpleNamespace(post=_view(*p)) for p in POSTS]
    ),
    "discovery pool": _discovery_block,
}


def _check(rendered: str) -> None:
    for uri, _, text, replies in POSTS:
        lines = [line for line in rendered.splitlines() if text in line]
        assert lines, f"{text!r} not shown"
        for line in lines:
            assert f"[{uri}]" in line, f"no uri on: {line}"
            if replies:
                count = f"{replies} {'reply' if replies == 1 else 'replies'}"
                assert count in line, f"no reply count on: {line}"


@pytest.mark.parametrize("surface", SURFACES)
def test_every_post_line_carries_uri_and_replies(surface):
    _check(SURFACES[surface]())


async def test_stranger_lookup_carries_uri_and_replies():
    _check(await _lookup_block())


def test_a_thread_marks_replies_it_did_not_load():
    """The root reports 2 replies with 1 loaded; that reply reports 1 with
    none loaded. Both gaps are marked with where to read from."""
    root = _ns(
        {
            "post": _view(*POSTS[0]),
            "replies": [{"post": _view(*POSTS[1]), "replies": []}],
        }
    )
    rendered = render_thread(root)
    assert f"1 more reply below, read-thread from [{POSTS[0][0]}]" in rendered
    assert f"1 more reply below, read-thread from [{POSTS[1][0]}]" in rendered


async def test_a_reply_below_the_root_fetch_still_reaches_phi():
    """bufo.uk's thread ran past the appview's 10-level cap from the root, so
    phi's own post in it, and the reply asking her to fix it, never showed."""
    deep_uri = "at://did:plc:d/app.bsky.feed.post/deep"
    root = _ns({"post": _view(*POSTS[0]), "replies": []})
    branch = SimpleNamespace(
        post=_view(deep_uri, "devlog.test", "fix your post", 0),
        parent=SimpleNamespace(post=_view(*POSTS[0]), parent=None),
        replies=[],
    )
    calls = []

    async def get_thread(uri, depth=10):
        calls.append(uri)
        return SimpleNamespace(thread=root if uri == POSTS[0][0] else branch)

    context, root_node = await fetch_thread_context(
        SimpleNamespace(get_thread=get_thread), POSTS[0][0], deep_uri
    )
    assert calls == [POSTS[0][0], deep_uri]
    assert root_node is root
    assert f"@devlog.test [{deep_uri}]: fix your post" in context
