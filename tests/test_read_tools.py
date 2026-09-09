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
    assert (
        out.splitlines()[0]
        == "@a.test [at://did:plc:a/app.bsky.feed.post/1] (3 likes, today): hello"
    )
    assert "@? [at://did:plc:b/app.bsky.feed.post/2] (0 likes): " in out


def test_day_bound_expands_dates_and_passes_instants() -> None:
    assert _day_bound("2026-08-18") == "2026-08-18T00:00:00Z"
    assert _day_bound("2026-08-18T12:00:00Z") == "2026-08-18T12:00:00Z"


def test_search_preserves_labeled_links_after_long_unicode_text() -> None:
    text = "🦆 " + "a" * 205 + "\nYes, more dignified\nView results"
    label = "Yes, more dignified"
    start = text.encode("utf-8").index(label.encode("utf-8"))
    post = {
        "record": {
            "text": text,
            "facets": [
                {
                    "index": {
                        "byteStart": start,
                        "byteEnd": start + len(label.encode("utf-8")),
                    },
                    "features": [
                        {
                            "$type": "app.bsky.richtext.facet#link",
                            "uri": "https://bsky.app/profile/results.feedpolls.org/feed/poll-example-opt-0",
                        }
                    ],
                }
            ],
        }
    }
    rendered = render_posts([post], date(2026, 9, 9))
    assert text in rendered
    assert (
        "link 'Yes, more dignified': https://bsky.app/profile/results.feedpolls.org/feed/poll-example-opt-0"
        in rendered
    )


def test_search_link_evidence_ignores_mentions_and_survives_missing_ranges() -> None:
    record = {
        "text": "an option",
        "facets": [
            {
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#mention",
                        "did": "did:plc:example",
                    },
                    {
                        "$type": "app.bsky.richtext.facet#link",
                        "uri": "https://example.com/option",
                    },
                ],
            }
        ],
    }
    rendered = render_posts([{"record": record}], date(2026, 9, 9))
    assert "https://example.com/option" in rendered
    assert "did:plc:example" not in rendered
