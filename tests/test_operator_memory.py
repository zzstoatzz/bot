"""The operator gets per-person memory like anyone else, across his accounts.

2026-10-19: asked on Delvetown about her formative relationships, Phi said her
memory of people was thin and listed the devlog account as someone separate.
`inject_user_memory` had skipped the owner since the April batch rewrite, so
39 observations and 88 exchanges about him never reached a batch run, and
nothing in context said the devlog account was him.
"""

from bot.agent import memory_queries
from bot.config import settings


def _entry(handle: str, text: str) -> dict:
    return {"author_handle": handle, "post_text": text}


def test_operator_post_recalls_every_operator_namespace():
    main, devlog = settings.operator_handles
    queries = memory_queries({"a": _entry(main, "who formed you?")})
    assert queries == {main: "who formed you?", devlog: "who formed you?"}


def test_phi_is_skipped_and_others_keep_their_own_query():
    queries = memory_queries(
        {
            "a": _entry(settings.bluesky_handle, "my own post"),
            "b": _entry("someone.bsky.social", "hi"),
            "c": _entry("someone.bsky.social", "again"),
        }
    )
    assert queries == {"someone.bsky.social": "hi again"}


def test_empty_text_falls_back_to_handle():
    queries = memory_queries({"a": _entry("someone.bsky.social", "")})
    assert queries == {"someone.bsky.social": "someone.bsky.social"}
