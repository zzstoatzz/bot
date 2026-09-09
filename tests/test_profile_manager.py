"""Tests for profile status marker handling.

Regression context: phi authors her own bio (up to bsky's 256-grapheme
cap) and the old pause/resume flow appended a 152-char capability
suffix to it, overflowing the cap — the PDS rejected the write and the
bio stayed "offline" while phi was online. Status flips must be
length-neutral.
"""

from unittest.mock import Mock

import pytest
from atproto import models

from bot.core.profile_manager import ProfileManager, _toggle_status_marker

PHI_AUTHORED_BIO = (
    "ai on fly.io. replies, remembers, follows threads. built and operated "
    "by @zzstoatzz.io. interested in small infrastructure, long-form "
    "writing, and connecting existing things. 🟢"
)


def test_offline_flips_green_to_red():
    assert _toggle_status_marker(PHI_AUTHORED_BIO, is_online=False) == (
        PHI_AUTHORED_BIO.replace("🟢", "🔴")
    )


def test_online_flips_red_to_green():
    offline = PHI_AUTHORED_BIO.replace("🟢", "🔴")
    assert _toggle_status_marker(offline, is_online=True) == PHI_AUTHORED_BIO


def test_online_collapses_legacy_offline_wording():
    legacy = (
        f"{PHI_AUTHORED_BIO.removesuffix(' 🟢')}\n\n"
        "source code: https://tangled.sh/zzstoatzz.io/bot\n\n🔴 offline"
    )
    result = _toggle_status_marker(legacy, is_online=True)
    assert "offline" not in result
    assert "🔴" not in result
    assert result.endswith("🟢")


def test_flip_never_grows_a_max_length_bio():
    max_length_bio = ("x" * 254 + " 🟢")[:256]
    for is_online in (True, False):
        flipped = _toggle_status_marker(max_length_bio, is_online)
        assert len(flipped) <= 256


def test_marker_free_bio_is_untouched():
    bio = "no markers here"
    assert _toggle_status_marker(bio, is_online=True) == bio
    assert _toggle_status_marker(bio, is_online=False) == bio


def _manager_with_bio(bio: str) -> tuple[ProfileManager, Mock]:
    client = Mock()
    client.me.did = "did:plc:test"
    record = models.AppBskyActorProfile.Record(
        description=bio, display_name="phi"
    )
    client.com.atproto.repo.get_record.return_value = Mock(value=record)
    return ProfileManager(client), client


async def test_set_online_status_writes_flipped_bio():
    pm, client = _manager_with_bio(PHI_AUTHORED_BIO)
    await pm.set_online_status(False)
    written = client.com.atproto.repo.put_record.call_args[0][0]["record"]
    assert written["description"] == PHI_AUTHORED_BIO.replace("🟢", "🔴")


async def test_set_online_status_skips_write_without_marker():
    pm, client = _manager_with_bio("no markers here")
    await pm.set_online_status(True)
    client.com.atproto.repo.put_record.assert_not_called()


@pytest.mark.parametrize("operation", ["status", "description", "label"])
async def test_profile_updates_preserve_pinned_post_and_unrecognized_fields(operation):
    pm, client = _manager_with_bio(PHI_AUTHORED_BIO)
    original = {
        "$type": "app.bsky.actor.profile",
        "description": PHI_AUTHORED_BIO,
        "displayName": "phi",
        "pinnedPost": {
            "uri": "at://did:plc:test/app.bsky.feed.post/pinned",
            "cid": "bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku",
        },
        "createdAt": "2026-01-01T00:00:00Z",
        "futureField": {"value": ["preserve", "this"]},
    }
    client.com.atproto.repo.get_record.return_value.value = (
        models.AppBskyActorProfile.Record.model_validate(original)
    )
    if operation == "status":
        await pm.set_online_status(False)
        expected = {**original, "description": PHI_AUTHORED_BIO.replace("🟢", "🔴")}
    elif operation == "description":
        await pm.set_description("a new bio")
        expected = {**original, "description": "a new bio"}
    else:
        await pm.initialize()
        expected = {**original, "labels": {
            "$type": "com.atproto.label.defs#selfLabels", "values": [{"val": "bot"}]
        }}
    written = client.com.atproto.repo.put_record.call_args[0][0]["record"]
    assert written == expected
