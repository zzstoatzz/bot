"""A reply's reference words retain their subject during episodic selection."""

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from bot.services import message_handler
from bot.tools._helpers import PhiDeps, notification_recall


@pytest.mark.parametrize("parent_state", ["ok", "missing", "changed", "error"])
async def test_parent_hydration_is_exact_and_failure_preserves_received_text(
    monkeypatch, parent_state
):
    parent_uri = "at://phi/app.bsky.feed.post/game"
    parent = NS(
        uri=parent_uri,
        cid="parent-cid",
        author=NS(handle="phi.test"),
        record=NS(text="I want to try the ragdoll game.", facets=[]),
    )
    post = NS(
        uri="at://operator/app.bsky.feed.post/reply",
        cid="reply-cid",
        author=NS(handle="operator.test", did="did:plc:operator"),
        record=NS(
            text="That site needs browser controls.",
            facets=[],
            reply=NS(
                parent=NS(uri=parent_uri, cid="parent-cid"),
                root=NS(uri="at://root", cid="root-cid"),
            ),
        ),
    )
    if parent_state == "changed":
        parent.cid = "different-version"
    lookup = (
        RuntimeError("offline")
        if parent_state == "error"
        else NS(posts=[] if parent_state == "missing" else [parent])
    )
    handler = message_handler.MessageHandler.__new__(message_handler.MessageHandler)
    handler.client = NS(
        get_posts=AsyncMock(side_effect=[NS(posts=[post]), lookup]),
        get_thread=AsyncMock(side_effect=RuntimeError("thread missing")),
    )
    monkeypatch.setattr(message_handler, "extract_cited_references", lambda _: [])
    entry = await handler._build_post_entry(NS(uri=post.uri, reason="reply"))
    assert entry["post_text"] == post.record.text
    query = notification_recall(
        PhiDeps(author_handle="", notifications_context={post.uri: entry})
    )
    assert post.record.text in query
    if parent_state == "ok":
        assert entry["reply_parent"]["cid"] == "parent-cid"
        assert parent.record.text in query
        assert parent_uri in query
    else:
        assert entry["reply_parent"] is None
        assert parent.record.text not in query


def test_distinct_events_and_citations_keep_their_own_subjects():
    deps = PhiDeps(
        author_handle="",
        notification_events=[
            {
                "uri": "at://one",
                "post_text": "that one",
                "reply_parent": {
                    "uri": "at://parent",
                    "author_handle": "a.test",
                    "text": "a game",
                },
            },
            {"uri": "at://two", "post_text": "another subject"},
        ],
    )
    query = notification_recall(deps)
    assert "a game" in query and "another subject" in query
    assert query.index("a game") < query.index("that one")
