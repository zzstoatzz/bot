from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from bot.core import etiquette, policy
from bot.tools import blog
from bot.tools import etiquette as etiquette_tools
from bot.tools.posting import _policy_gate


@pytest.fixture(autouse=True)
def private_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(etiquette, "JOURNAL", tmp_path / "journal.sqlite3")


async def test_rejection_requires_exact_private_note_before_new_judgment(monkeypatch):
    judge = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(
                output={
                    "verdict": "block",
                    "policy": "public-etiquette",
                    "reason": "This is an explanatory essay.",
                }
            )
        )
    )
    monkeypatch.setattr(policy, "_get_judge", lambda: judge)
    first = await policy.check_action("essay", "invited", tool="post")
    second = await policy.check_action("different draft", "invited", tool="post")
    assert second["attempt_id"] == first["attempt_id"]
    assert judge.run.await_count == 1
    note = "I explained the lesson. I will make one joke about the missing cursor."
    assert "stored verbatim" in etiquette.document(first["attempt_id"], note)
    assert "already documented" in etiquette.document(first["attempt_id"], "overwrite")
    with etiquette.connect() as db:
        assert db.execute("SELECT note FROM attempts").fetchone()[0] == note
    judge.run.return_value = SimpleNamespace(
        output={
            "verdict": "allow",
            "public_form": "deadpan-bit",
            "form_evidence": "specific comic turn",
        }
    )
    await policy.check_action("a revised bit", "invited", tool="post")
    stats = etiquette.board()
    assert stats["counts"] == {"allow": 1, "block": 1}
    assert stats["pending"] == 0
    assert note not in str(stats)
    assert "different draft" not in str(stats)


async def test_classifier_outage_never_allows_invited_publication(monkeypatch):
    judge = SimpleNamespace(run=AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr(policy, "_get_judge", lambda: judge)
    refusal, _ = await _policy_gate("draft", "invited", unprompted=False)
    assert refusal and "fail-closed" in refusal
    assert etiquette.board()["counts"] == {"error": 1}
    assert etiquette.pending() == []


async def test_likes_and_internal_notes_are_not_held_by_public_rejection(monkeypatch):
    etiquette.record("post", "block", "public-etiquette", "essay")
    judge = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(
                output={
                    "verdict": "allow",
                    "public_form": "deadpan-bit",
                    "form_evidence": "specific comic turn",
                }
            )
        )
    )
    monkeypatch.setattr(policy, "_get_judge", lambda: judge)
    result = await policy.check_action("like", "invited", tool="like")
    assert result["verdict"] == "allow"
    assert etiquette.board()["counts"] == {"block": 1}


async def test_blog_classifier_rejection_precedes_pds_write(monkeypatch):
    registered = {}
    blog.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    monkeypatch.setattr(
        blog, "get_override", AsyncMock(return_value={"active": False, "message": ""})
    )
    monkeypatch.setattr(
        blog, "_policy_gate", AsyncMock(return_value=("PUBLIC ACTION REJECTED", ""))
    )
    authenticate = AsyncMock()
    monkeypatch.setattr(blog.bot_client, "authenticate", authenticate)
    response = await registered["publish_blog_post"](
        SimpleNamespace(deps=None), "title", "body"
    )
    assert response == "PUBLIC ACTION REJECTED"
    authenticate.assert_not_awaited()


def test_revision_tool_registers_with_real_harness():
    agent = Agent(TestModel())
    etiquette_tools.register(agent)
    assert "document_public_revision" in agent._function_toolset.tools


def test_raw_blog_updates_cannot_skip_classifier():
    from bot.core.mcp_guard import _structural_refusal

    assert "publish_blog_post" in (
        _structural_refusal(
            "pdsx",
            "update_record",
            {
                "uri": "at://did:plc:phi/app.greengale.document/abc",
                "updates": {"content": "essay"},
            },
        )
        or ""
    )
    assert "post" in (
        _structural_refusal(
            "pdsx",
            "update_record",
            {"uri": "app.bsky.feed.post/abc", "updates": {"text": "essay"}},
        )
        or ""
    )


async def test_profile_text_update_is_classified_but_image_patch_is_not(monkeypatch):
    from bot.core import mcp_guard
    from bot.tools import posting

    monkeypatch.setattr(
        mcp_guard,
        "get_override",
        AsyncMock(return_value={"active": False, "message": ""}),
    )
    classifier = AsyncMock(return_value=("PUBLIC ACTION REJECTED", ""))
    monkeypatch.setattr(posting, "_policy_gate", classifier)
    invoke = AsyncMock(return_value="updated")
    guard = mcp_guard.make_mcp_guard("pdsx", "test")
    context = SimpleNamespace(deps=None)
    refusal = await guard(
        context,
        invoke,
        "update_record",
        {"uri": "app.bsky.actor.profile/self", "updates": {"description": "essay"}},
    )
    assert refusal == "PUBLIC ACTION REJECTED"
    invoke.assert_not_awaited()
    assert (
        await guard(
            context,
            invoke,
            "update_record",
            {
                "uri": "app.bsky.actor.profile/self",
                "updates": {"avatar": {"ref": "blob"}},
            },
        )
        == "updated"
    )
    assert classifier.await_count == 1


async def test_split_source_overflow_is_checked_before_any_publication(monkeypatch):
    from bot.tools import posting

    registered = {}
    posting.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    monkeypatch.setattr(
        posting,
        "get_override",
        AsyncMock(return_value={"active": False, "message": ""}),
    )
    monkeypatch.setattr(posting, "_recent_own_posts", lambda: "")
    monkeypatch.setattr(posting, "coverage_note", AsyncMock(return_value=""))
    judge = AsyncMock(
        side_effect=[
            {"verdict": "allow"},
            {
                "verdict": "block",
                "policy": "public-etiquette",
                "reason": "The second post only contains sources.",
                "attempt_id": "overflow",
            },
        ]
    )
    monkeypatch.setattr(posting, "check_action", judge)
    publish = AsyncMock()
    monkeypatch.setattr(posting.bot_client, "create_post", publish)
    from bot.tools._helpers import PhiDeps

    draft = "j" * 210 + "\n" + "https://example.org/" + "s" * 170
    result = await registered["post"](
        SimpleNamespace(deps=PhiDeps(author_handle="")), draft
    )
    assert "PUBLIC ACTION REJECTED" in result
    assert judge.await_count == 2
    assert "j" * 210 not in judge.await_args.kwargs["action"]
    publish.assert_not_awaited()
