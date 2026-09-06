"""Regression tests for the pre-action policy gate (bot.core.policy +
bot.tools.posting._policy_gate).

Trigger incident (2026-06-30): a model upgrade turned a never-written norm
("don't enter strangers' threads uninvited") into an unprompted reply from a
scheduled cycle. The gate is the actor/judge split that makes the policies
enforceable without hard-coding them.
"""

from typing import Literal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.core.policy import PolicySlug, PolicyVerdict
from bot.memory.namespace_memory import NamespaceMemory
from bot.tools import posting
from bot.tools.posting import _policy_gate, _reply_provenance


def _verdict(
    v: Literal["allow", "warn", "block"],
    policy: PolicySlug | None = None,
    reason: str | None = None,
) -> PolicyVerdict:
    out: PolicyVerdict = {"verdict": v}
    if policy is not None:
        out["policy"] = policy
    if reason is not None:
        out["reason"] = reason
    return out


async def test_block_refuses_and_names_policy():
    with patch.object(
        posting,
        "check_action",
        AsyncMock(return_value=_verdict("block", "uninvited-reply", "nobody asked.")),
    ):
        refusal, note = await _policy_gate("reply to x", "unprompted", unprompted=True)
    assert refusal is not None
    assert "uninvited-reply" in refusal
    assert "nobody asked." in refusal
    assert "nothing was posted" in refusal
    assert note == ""


async def test_warn_passes_with_note():
    with patch.object(
        posting,
        "check_action",
        AsyncMock(return_value=_verdict("warn", "bliss-attractor", "third one today.")),
    ):
        refusal, note = await _policy_gate("post: ...", "top-level", unprompted=True)
    assert refusal is None
    assert "bliss-attractor" in note
    assert "third one today." in note


async def test_allow_is_clean():
    with patch.object(
        posting, "check_action", AsyncMock(return_value=_verdict("allow"))
    ):
        refusal, note = await _policy_gate("post: hi", "invited", unprompted=False)
    assert refusal is None
    assert note == ""


async def test_judge_failure_fails_closed_when_unprompted():
    with patch.object(
        posting, "check_action", AsyncMock(side_effect=RuntimeError("judge down"))
    ):
        refusal, note = await _policy_gate("post: ...", "cycle", unprompted=True)
    assert refusal is not None
    assert "fail-closed" in refusal
    assert note == ""


async def test_judge_failure_fails_closed_for_invited_public_text():
    with patch.object(
        posting, "check_action", AsyncMock(side_effect=RuntimeError("judge down"))
    ):
        refusal, note = await _policy_gate("reply: ...", "batch", unprompted=False)
    assert refusal and "fail-closed" in refusal
    assert note == ""


def test_reply_provenance_batch_is_invited():
    notifs = {
        "at://did:plc:abc/app.bsky.feed.post/1": {
            "author_handle": "pds.dad",
            "reason": "mention",
        }
    }
    p = _reply_provenance("at://did:plc:abc/app.bsky.feed.post/1", notifs)
    assert "invited" in p
    assert "@pds.dad" in p


def test_reply_provenance_out_of_batch_is_unprompted():
    p = _reply_provenance("at://did:plc:stranger/app.bsky.feed.post/1", {})
    assert "unprompted" in p
    assert "timeline" not in p


DEVLOG = "did:plc:o53crari67ge7bvbv273lxln"


def _devlog_post(text):
    return {
        "at://did:plc:o53crari67ge7bvbv273lxln/app.bsky.feed.post/3dev": {
            "author_handle": "zzstoatzzdevlog.bsky.social",
            "author_did": DEVLOG,
            "reason": "mention",
            "post_text": text,
        }
    }


def test_operator_post_naming_the_target_is_direction():
    """2026-09-02: the devlog told phi to post a one-line reply under a
    stranger's post; the provenance said the target was found "via
    timeline/search" and the judge blocked it. the operator's post in the
    batch pointing at the target is authorization, and the judge must be
    told so."""
    p = _reply_provenance(
        "at://did:plc:stranger/app.bsky.feed.post/3mukyxgccuc2g",
        _devlog_post("create a fresh reply to noah's post (3mukyxgccuc2g), one line"),
    )
    assert "operator directed" in p
    assert "unprompted" not in p


def test_operator_post_naming_the_thread_root_is_direction():
    p = _reply_provenance(
        "at://did:plc:stranger/app.bsky.feed.post/3leaf",
        _devlog_post("reply in https://bsky.app/profile/x/post/3root please"),
        root_uri="at://did:plc:host/app.bsky.feed.post/3root",
    )
    assert "operator directed" in p


def test_stranger_post_naming_the_target_is_not_direction():
    notifs = _devlog_post("go reply to 3mukyxgccuc2g")
    for entry in notifs.values():
        entry["author_did"] = "did:plc:someoneelse"
    p = _reply_provenance(
        "at://did:plc:stranger/app.bsky.feed.post/3mukyxgccuc2g", notifs
    )
    assert "unprompted" in p


def test_operator_post_about_something_else_is_not_direction():
    p = _reply_provenance(
        "at://did:plc:stranger/app.bsky.feed.post/3mukyxgccuc2g",
        _devlog_post("nice post today"),
    )
    assert "unprompted" in p


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestOperatorAuthorizationNote:
    """regression (2026-07-21): the judge blocked the botnana introduction
    minutes after the operator's like authorized it — the like lived only in
    phi's reasoning and never reached the judge's provenance."""

    def test_owner_like_in_batch_surfaces_authorization(self):
        from bot.config import settings
        from bot.tools.posting import _operator_authorization_note

        note = _operator_authorization_note(
            {
                "at://x/app.bsky.feed.post/1": {
                    "reason": "like",
                    "author_handle": settings.owner_handle,
                    "post_text": "like this to authorize tagging @someone",
                }
            }
        )
        assert "operator" in note
        assert "authorize tagging @someone" in note

    def test_stranger_like_is_not_authorization(self):
        from bot.tools.posting import _operator_authorization_note

        assert (
            _operator_authorization_note(
                {
                    "at://x/1": {
                        "reason": "like",
                        "author_handle": "stranger.bsky.social",
                        "post_text": "like this to authorize",
                    },
                    "at://x/2": {
                        "reason": "reply",
                        "author_handle": "zzstoatzz.io",
                        "post_text": "not a like",
                    },
                }
            )
            == ""
        )


class TestSelfRepeat:
    """regression (2026-08-18, 2026-08-20): phi restated her own 08-16
    gerakines post two days later and her own 18:03 apenwarr post an hour
    later. The prior-coverage index existed both times but was only ever
    queried by incoming material — on 08-18 it surfaced five chicken-market
    posts off a feed blob and missed the one that mattered. The draft itself
    is now the query, and the judge gets the result as self-repeat evidence."""

    COVERAGE = (
        "[PRIOR COVERAGE — ...]\n"
        '- 2026-08-16T14:02 (1.5d ago, top-level post): "nick gerakines on '
        "atproto's permissioned-data spaces: removing a member doesn't "
        'revoke anything"'
    )

    async def test_top_level_post_queries_coverage_with_the_draft(self):
        from bot.tools._helpers import PhiDeps

        captured = {}

        class FakeAgent:
            def tool(self, fn):
                captured[fn.__name__] = fn
                return fn

        posting.register(FakeAgent())
        memory = Mock(spec=NamespaceMemory)
        ctx = type("Ctx", (), {"deps": PhiDeps(author_handle="", memory=memory)})()
        draft = (
            "nick gerakines's point yesterday: removing someone doesn't revoke anything"
        )

        with (
            patch.object(
                posting, "get_override", AsyncMock(return_value={"active": False})
            ),
            patch.object(
                posting, "coverage_note", AsyncMock(return_value=self.COVERAGE)
            ) as recall,
            patch.object(
                posting,
                "check_action",
                AsyncMock(
                    return_value=_verdict(
                        "block", "self-repeat", "you said this on the 16th."
                    )
                ),
            ) as judge,
            patch.object(posting, "_recent_own_posts", lambda: ""),
            patch.object(posting.bot_client, "create_post", AsyncMock()) as create,
        ):
            result = await captured["post"](ctx, draft)

        recall.assert_awaited_once_with(memory, draft)
        assert judge.await_args.kwargs["prior_coverage"] == self.COVERAGE
        assert "self-repeat" in result
        assert "you said this on the 16th." in result
        create.assert_not_called()

    async def test_reply_does_not_query_coverage(self):
        from bot.tools._helpers import PhiDeps

        captured = {}

        class FakeAgent:
            def tool(self, fn):
                captured[fn.__name__] = fn
                return fn

        posting.register(FakeAgent())
        ctx = type("Ctx", (), {"deps": PhiDeps(author_handle="someone")})()

        with (
            patch.object(
                posting, "get_override", AsyncMock(return_value={"active": False})
            ),
            patch.object(posting, "coverage_note", AsyncMock()) as recall,
            patch.object(
                posting,
                "_resolve_post_ref",
                AsyncMock(
                    return_value=(
                        "bafyp",
                        "at://did:plc:x/app.bsky.feed.post/r",
                        "bafyr",
                        "someone",
                        "hi",
                    )
                ),
            ),
            patch.object(
                posting,
                "check_action",
                AsyncMock(return_value=_verdict("block", "pile-on", "no.")),
            ) as judge,
            patch.object(posting, "_recent_own_posts", lambda: ""),
        ):
            await captured["post"](
                ctx, "a reply", in_reply_to="at://did:plc:x/app.bsky.feed.post/r"
            )

        recall.assert_not_called()
        assert judge.await_args.kwargs["prior_coverage"] == ""

    async def test_judge_prompt_carries_coverage_as_evidence(self):
        from bot.core import policy

        seen = {}

        class FakeJudge:
            async def run(self, prompt):
                seen["prompt"] = prompt
                return type("R", (), {"output": _verdict("allow")})()

        with patch.object(policy, "_get_judge", lambda: FakeJudge()):
            await policy.check_action(
                "top-level post: ...", "scheduled", prior_coverage=self.COVERAGE
            )
        assert "self-repeat" in seen["prompt"]
        assert self.COVERAGE in seen["prompt"]

        with patch.object(policy, "_get_judge", lambda: FakeJudge()):
            await policy.check_action("top-level post: ...", "scheduled")
        assert "evidence for self-repeat" not in seen["prompt"]


async def test_pull_comment_text_reaches_the_prompt():
    """2026-08-21 18:46: woken for the devlog's reset comment, phi reported on
    the operator's older comment instead — event_material only keyed memory
    recall and was never rendered, so every review run worked blind."""
    from unittest.mock import AsyncMock

    from bot.agent import PhiAgent

    agent = PhiAgent.__new__(PhiAgent)
    agent.memory = None
    agent._run_agent = AsyncMock(return_value="ok")
    material = "@zzstoatzzdevlog.bsky.social commented on your pull request at://x/sh.tangled.repo.pull/1:\n\nstart over from round 1"
    await agent.process_pull_comment(material)
    prompt = agent._run_agent.await_args.kwargs["prompt"]
    assert "[REVIEW COMMENT]" in prompt and "start over from round 1" in prompt
    assert agent._run_agent.await_args.kwargs["deps"].event_material == material
