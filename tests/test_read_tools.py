from __future__ import annotations

from datetime import date

from bot.tools.search import _day_bound, render_posts


def test_render_posts_survives_embed_types_the_sdk_does_not_know() -> None:
    posts = [
        {
            "uri": "at://did:plc:a/app.bsky.feed.post/1",
            "author": {"handle": "a.test"},
            "record": {"text": "hello"},
            "likeCount": 3,
            "indexedAt": "2026-09-03T10:00:00Z",
            "embed": {"$type": "app.bsky.embed.gallery#view", "items": []},
        },
        {"uri": "at://did:plc:b/app.bsky.feed.post/2", "author": {}, "record": {}},
    ]
    out = render_posts(posts, date(2026, 9, 3))
    assert out.splitlines()[0] == "@a.test [at://did:plc:a/app.bsky.feed.post/1] (3 likes, today): hello"
    assert "@? [at://did:plc:b/app.bsky.feed.post/2] (0 likes): " in out


def test_day_bound_expands_dates_and_passes_instants() -> None:
    assert _day_bound("2026-08-18") == "2026-08-18T00:00:00Z"
    assert _day_bound("2026-08-18T12:00:00Z") == "2026-08-18T12:00:00Z"
