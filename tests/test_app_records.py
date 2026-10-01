"""Records in a Bluesky-shaped app get the checks their app.bsky twins get.

A `town.delve.feed.post` is a public post written as an ordinary pdsx record.
Before this, the guard governed only `app.bsky.feed.*`, so a post, like, or
repost in any forked app went out with no judge.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.config import settings
from bot.core import app_records, mcp_guard
from bot.core.app_records import governed_shape

MY_DID = "did:plc:65sucjiel52gefhcdcypynsr"
THEIR_POST = "at://did:plc:someone/town.delve.feed.post/3abc"
PASS = AsyncMock(return_value=(None, ""))


@pytest.fixture
def calls(monkeypatch):
    async def get_override():
        return {"active": False, "message": "", "updatedAt": ""}

    client = SimpleNamespace(me=SimpleNamespace(did=MY_DID))
    monkeypatch.setattr(mcp_guard, "get_override", get_override)
    monkeypatch.setattr(app_records, "bot_client", SimpleNamespace(client=client))
    return []


async def write(calls, name, args, gate=PASS, ctx=None):
    async def call_tool(tool, sent, _):
        calls.append((tool, sent))
        return "ok"

    guard = mcp_guard.make_mcp_guard("pdsx", "test")
    with patch("bot.tools.posting._policy_gate", gate):
        return await guard(ctx, call_tool, name, args)


def judged(gate: AsyncMock):
    assert gate.await_args is not None, "the judge was never asked"
    return gate.await_args


def mention(did: str) -> dict:
    return {
        "index": {"byteStart": 0, "byteEnd": 4},
        "features": [{"$type": "town.delve.richtext.facet#mention", "did": did}],
    }


def test_shapes_are_recognized_outside_bluesky_only():
    assert governed_shape("town.delve.feed.post") == "feed.post"
    assert governed_shape("social.other.feed.repost") == "feed.repost"
    assert governed_shape("town.delve.actor.profile") == "actor.profile"
    assert governed_shape("app.bsky.feed.post") is None
    assert governed_shape("town.delve.graph.follow") is None
    assert governed_shape("network.cosmik.card") is None


async def test_a_post_goes_to_the_judge_before_it_is_written(calls):
    gate = AsyncMock(return_value=(None, ""))
    args = {"collection": "town.delve.feed.post", "record": {"text": "hi delve"}}
    assert await write(calls, "create_record", args, gate) == "ok"
    assert judged(gate).args[0] == "hi delve"
    assert "town.delve" in judged(gate).args[1]
    assert judged(gate).kwargs["tool"] == "post"
    assert judged(gate).kwargs["unprompted"] is True
    assert calls == [("create_record", args)]


async def test_the_judge_can_block_a_post(calls):
    gate = AsyncMock(return_value=("refused: not this", ""))
    for name, args in (
        (
            "create_record",
            {"collection": "town.delve.feed.post", "record": {"text": "x"}},
        ),
        (
            "update_record",
            {
                "uri": f"at://{MY_DID}/town.delve.feed.post/3abc",
                "updates": {"text": "x"},
            },
        ),
    ):
        assert await write(calls, name, args, gate) == "refused: not this"
    assert calls == []


async def test_a_judge_warning_rides_on_the_result(calls):
    gate = AsyncMock(return_value=(None, " [policy note: close to the line]"))
    args = {"collection": "town.delve.feed.post", "record": {"text": "hi"}}
    assert await write(calls, "create_record", args, gate) == (
        "ok [policy note: close to the line]"
    )


async def test_a_post_cannot_mention_a_stranger(calls):
    gate = AsyncMock(return_value=(None, ""))
    record = {"text": "@you hi", "facets": [mention("did:plc:stranger")]}
    result = await write(
        calls,
        "create_record",
        {"collection": "town.delve.feed.post", "record": record},
        gate,
    )
    assert "mention consent is not set up for town.delve" in result
    gate.assert_not_awaited()
    assert calls == []


async def test_a_post_can_mention_the_operator(calls):
    record = {"text": "@nate hi", "facets": [mention(settings.operator_dids[0])]}
    args = {"collection": "town.delve.feed.post", "record": record}
    assert (
        await write(calls, "create_record", args, AsyncMock(return_value=(None, "")))
        == "ok"
    )


async def test_a_reply_names_its_parent_as_a_contact(calls):
    gate = AsyncMock(return_value=(None, ""))
    record = {"text": "hello", "reply": {"parent": {"uri": THEIR_POST, "cid": "c"}}}
    ctx = SimpleNamespace(
        deps=SimpleNamespace(notifications_context={"x": {}}, author_handle="")
    )
    await write(
        calls,
        "create_record",
        {"collection": "town.delve.feed.post", "record": record},
        gate,
        ctx,
    )
    assert judged(gate).kwargs["contacts"] == [{"uri": THEIR_POST, "evidence": ""}]
    assert judged(gate).kwargs["unprompted"] is False


@pytest.mark.parametrize("verb", ["like", "repost"])
async def test_a_reaction_is_verified_judged_and_completed(calls, verb):
    gate = AsyncMock(return_value=(None, ""))
    fetched = {"uri": THEIR_POST, "cid": "bafyreal", "value": {"text": "their words"}}
    with patch.object(app_records, "fetch_record", AsyncMock(return_value=fetched)):
        result = await write(
            calls,
            "create_record",
            {
                "collection": f"town.delve.feed.{verb}",
                "record": {"subject": {"uri": THEIR_POST}},
            },
            gate,
        )
    assert result == "ok"
    assert judged(gate).kwargs["tool"] == verb
    assert "their words" in judged(gate).args[0]
    sent = calls[0][1]["record"]
    assert sent["subject"] == {"uri": THEIR_POST, "cid": "bafyreal"}
    assert sent["createdAt"]


async def test_a_reaction_to_nothing_or_to_herself_is_refused(calls):
    gate = AsyncMock(return_value=(None, ""))
    collection = "town.delve.feed.like"
    missing = await write(
        calls, "create_record", {"collection": collection, "record": {}}, gate
    )
    assert "needs record.subject.uri" in missing
    own = {"subject": {"uri": f"at://{MY_DID}/town.delve.feed.post/3abc"}}
    assert "your own post" in await write(
        calls, "create_record", {"collection": collection, "record": own}, gate
    )
    with patch.object(
        app_records, "fetch_record", AsyncMock(side_effect=ValueError("nope"))
    ):
        unverified = await write(
            calls,
            "create_record",
            {"collection": collection, "record": {"subject": {"uri": THEIR_POST}}},
            gate,
        )
    assert "could not verify" in unverified
    gate.assert_not_awaited()
    assert calls == []


async def test_profile_text_is_judged(calls):
    gate = AsyncMock(return_value=("refused: no", ""))
    args = {
        "collection": "town.delve.actor.profile",
        "record": {"displayName": "phi", "description": "an owl"},
    }
    assert await write(calls, "create_record", args, gate) == "refused: no"
    assert judged(gate).args[0] == "phi\nan owl"
    assert calls == []


async def test_other_records_in_the_same_app_still_pass(calls):
    gate = AsyncMock(return_value=("refused: should not be asked", ""))
    args = {"collection": "town.delve.graph.follow", "record": {"subject": "did:plc:x"}}
    assert await write(calls, "create_record", args, gate) == "ok"
    gate.assert_not_awaited()
