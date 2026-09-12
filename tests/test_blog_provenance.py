"""The judge can distinguish an invited essay from an unsolicited report."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.tools import blog
from bot.tools._helpers import PhiDeps


@pytest.mark.parametrize("private", [False, True])
async def test_requested_article_context_reaches_gate_without_bypassing_it(
    monkeypatch, private
):
    text = "Take your time with a piece about the last month; publish when ready."
    deps = PhiDeps(author_handle="nate.example")
    if private:
        deps.private_message_context = text
    else:
        deps.notifications_context = {
            "at://request": {
                "post_text": text,
                "author_handle": "nate.example",
                "reason": "reply",
                "thread_context": "Earlier discussion",
            }
        }
    registered = {}
    blog.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    monkeypatch.setattr(blog, "get_override", AsyncMock(return_value={"active": False}))
    gate = AsyncMock(return_value=("blocked for private contents", ""))
    monkeypatch.setattr(blog, "_policy_gate", gate)
    auth = AsyncMock()
    monkeypatch.setattr(blog.bot_client, "authenticate", auth)
    result = await registered["publish_blog_post"](
        SimpleNamespace(deps=deps), "A month", "draft"
    )
    assert result == "blocked for private contents"
    auth.assert_not_awaited()
    args = gate.await_args
    assert args is not None
    assert text in args.args[1]
    assert "GreenGale" in args.args[1]
    assert args.kwargs["unprompted"] is False
    assert args.kwargs["tool"] == "publish_blog_post"
    assert "unrelated request" in args.args[1]


def test_no_invitation_is_not_invented():
    assert "No received invitation" in blog._blog_provenance(PhiDeps(author_handle=""))
