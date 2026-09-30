"""[RECENT OPERATIONS] shows top-level posts by topic, never her sentences.

Phi proposed this in the 2026-09-30 voice thread: the block kept her own
recent prose in every prompt. A label keeps the subject recognisable for
dedup; a failed label must fall back to the preview so continuity holds.
"""

from unittest.mock import AsyncMock, patch

import pytest

from bot.core import recent_operations as ro

POST_TEXT = (
    "The plagiarism was airtight. The linux box was not. https://example.com/writeup"
)


def _rows(text: str = POST_TEXT) -> list[ro._Row]:
    value = {"text": text}
    return [
        ro._Row(
            rkey="3post",
            nsid="app.bsky.feed.post",
            created_at="2026-09-29T18:00:00+00:00",
            summary=ro._summarize("app.bsky.feed.post", value),
            op="create",
            local=True,
            post_text=ro._top_level_text("app.bsky.feed.post", value),
        ),
        ro._Row(
            rkey="3reply",
            nsid="app.bsky.feed.post",
            created_at="2026-09-29T18:05:00+00:00",
            summary=ro._summarize(
                "app.bsky.feed.post", {"text": "hi", "reply": {"root": {}}}
            ),
            op="create",
            local=True,
            post_text="",
        ),
    ]


@pytest.fixture(autouse=True)
def _clear_cache():
    ro._topic_cache.clear()
    yield
    ro._topic_cache.clear()


async def test_labelled_post_renders_topic_without_her_prose():
    label = AsyncMock(return_value="plagiarism case, linux box compromise")
    with patch.object(ro, "_label_topic", label):
        block = ro._render(await ro._apply_topic_labels(_rows()))

    assert "topic: plagiarism case, linux box compromise" in block
    assert "airtight" not in block
    assert "[linked: example.com/writeup]" in block
    assert "reply (2 chars)" not in block  # replies still tally
    assert "routine (48h): replies ×1" in block


async def test_label_keeps_facet_link_targets():
    value = {
        "text": "writeup at example.com/wri...",
        "facets": [{"features": [{"uri": "https://example.com/writeup/full-path"}]}],
    }
    row = ro._Row(
        rkey="3post",
        nsid="app.bsky.feed.post",
        created_at="2026-09-29T18:00:00+00:00",
        summary=ro._summarize("app.bsky.feed.post", value),
        op="create",
        local=True,
        post_text=ro._top_level_text("app.bsky.feed.post", value),
    )
    with patch.object(ro, "_label_topic", AsyncMock(return_value="a writeup")):
        [labelled] = await ro._apply_topic_labels([row])

    assert labelled["summary"] == (
        "top-level post, topic: a writeup [linked: example.com/writeup/full-path]"
    )


async def test_failed_label_keeps_the_preview():
    with patch.object(ro, "_label_topic", AsyncMock(return_value="")):
        block = ro._render(await ro._apply_topic_labels(_rows()))

    assert '"The plagiarism was airtight.' in block


async def test_each_post_is_labelled_once():
    label = AsyncMock(return_value="plagiarism case")
    with patch.object(ro, "_label_topic", label):
        await ro._apply_topic_labels(_rows())
        await ro._apply_topic_labels(_rows())

    assert label.await_count == 1


async def test_cache_drops_posts_that_left_the_window():
    with patch.object(ro, "_label_topic", AsyncMock(return_value="old topic")):
        await ro._apply_topic_labels(_rows("an older post"))
    with patch.object(ro, "_label_topic", AsyncMock(return_value="new topic")):
        await ro._apply_topic_labels(_rows("a newer post"))

    assert list(ro._topic_cache) == ["a newer post"]


def test_ops_log_rows_carry_top_level_text_only():
    rows = ro._rows_from_ops(
        [
            {
                "nsid": "app.bsky.feed.post",
                "rkey": "a",
                "at": "2026-09-29T18:00:00+00:00",
                "time_us": 1,
                "rev": "r1",
                "op": "create",
                "local": True,
                "record": {"text": "top level  text"},
            },
            {
                "nsid": "app.bsky.feed.post",
                "rkey": "b",
                "at": "2026-09-29T18:01:00+00:00",
                "time_us": 2,
                "rev": "r2",
                "op": "create",
                "local": True,
                "record": {"text": "a reply", "reply": {"root": {}}},
            },
            {
                "nsid": "app.bsky.feed.post",
                "rkey": "a",
                "at": "2026-09-29T18:02:00+00:00",
                "time_us": 3,
                "rev": "r3",
                "op": "delete",
                "local": True,
                "record": None,
            },
        ]
    )
    assert [r["post_text"] for r in rows] == ["top level text", "", ""]
