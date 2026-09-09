"""A publication cannot borrow another destination's invitation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.core import policy
from bot.tools import posting
from bot.tools._helpers import PhiDeps

OWN = "did:plc:phi"
INVITED = "at://did:plc:friend/app.bsky.feed.post/one"
STRANGER = "at://did:plc:stranger/app.bsky.feed.post/two"


@pytest.mark.parametrize(
    "description", ["reply", "top-level post", "future delivery adapter"]
)
async def test_missing_contact_authority_blocks_even_if_judge_would_allow(description):
    judge = SimpleNamespace(run=AsyncMock())
    with (
        patch.object(policy, "_get_judge", return_value=judge),
        patch.object(policy.etiquette, "pending", return_value=[]),
        patch.object(policy.etiquette, "record", return_value="attempt") as record,
    ):
        result = await policy.check_action(
            description,
            "an invited conversation",
            tool="post",
            contacts=[
                {"uri": INVITED, "evidence": "Current notification."},
                {"uri": STRANGER, "evidence": ""},
            ],
        )
    assert result["verdict"] == "block"
    assert result["policy"] == "uninvited-reply"
    assert STRANGER in result["reason"]
    judge.run.assert_not_called()
    record.assert_called_once()


def test_discovery_and_bot_label_are_not_authority():
    with patch.object(posting.bot_client, "client", SimpleNamespace(me=None)):
        contact = posting._publication_contact(
            STRANGER, {STRANGER: {"reason": "like", "labels": ["bot"]}}
        )
    assert contact["evidence"] == ""


async def test_invitation_still_goes_through_judge():
    judge = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(
                output={
                    "verdict": "allow",
                    "public_form": "direct-turn",
                }
            )
        )
    )
    with (
        patch.object(policy, "_get_judge", return_value=judge),
        patch.object(policy.etiquette, "pending", return_value=[]),
        patch.object(policy.etiquette, "record", return_value="attempt"),
    ):
        result = await policy.check_action(
            "publication",
            "",
            tool="post",
            contacts=[{"uri": INVITED, "evidence": "Current notification."}],
        )
    assert result["verdict"] == "allow"
    assert INVITED in judge.run.call_args.args[0]


@pytest.mark.parametrize("reply", [False, True])
async def test_quote_destination_reaches_shared_gate_even_with_invited_parent(reply):
    registered = {}
    posting.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    ctx = SimpleNamespace(
        deps=PhiDeps(
            author_handle="friend.test",
            notifications_context={
                INVITED: {"reason": "mention", "author_handle": "friend.test"},
            }
        )
    )
    source = SimpleNamespace(
        uri=STRANGER,
        cid="cid",
        author=SimpleNamespace(handle="stranger.test"),
        record=SimpleNamespace(text="source"),
    )
    with (
        patch.object(
            posting, "get_override", AsyncMock(return_value={"active": False})
        ),
        patch.object(
            posting.bot_client, "client", SimpleNamespace(me=SimpleNamespace(did=OWN))
        ),
        patch.object(
            posting.bot_client,
            "get_posts",
            AsyncMock(return_value=SimpleNamespace(posts=[source])),
        ),
        patch.object(
            posting,
            "_resolve_post_ref",
            AsyncMock(return_value=("cid", INVITED, "cid", "friend.test", "hi")),
        ),
        patch.object(posting, "coverage_note", AsyncMock(return_value="")),
        patch.object(
            posting, "_policy_gate", AsyncMock(return_value=("blocked", ""))
        ) as gate,
        patch.object(posting.bot_client, "create_post", AsyncMock()) as create,
    ):
        await registered["post"](
            ctx, "a question", quote=STRANGER, in_reply_to=INVITED if reply else ""
        )
    contacts = gate.call_args.kwargs["contacts"]
    assert {"uri": STRANGER, "evidence": ""} in contacts
    assert len(contacts) == (2 if reply else 1)
    create.assert_not_called()
