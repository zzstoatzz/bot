"""Regression test: mention facets respect the consent allowlist.

The allowlist ensures phi only sends notifications to people who consented
to interact — the conversation participant, the bot owner, and the bot itself.
Third-party handles appear as plain text, not clickable mentions.
"""

from types import SimpleNamespace

from bot.core.rich_text import parse_mentions


def _mock_resolve(handle: str):
    """Fake DID resolution — returns a predictable DID for any handle."""
    return SimpleNamespace(did=f"did:plc:fake-{handle.replace('.', '-')}")


def _make_client():
    """Minimal mock client with resolve_handle."""
    client = SimpleNamespace()
    client.com = SimpleNamespace()
    client.com.atproto = SimpleNamespace()
    client.com.atproto.identity = SimpleNamespace()
    client.com.atproto.identity.resolve_handle = lambda params: _mock_resolve(
        params["handle"]
    )
    return client


def test_allowlist_filters_third_party():
    """Handles not in the allowlist should NOT get mention facets."""
    text = "interesting point by @stranger.bsky.social and @friend.bsky.social"
    client = _make_client()

    facets = parse_mentions(text, client, allowed_handles={"friend.bsky.social"})

    assert len(facets) == 1
    assert facets[0]["features"][0]["did"] == "did:plc:fake-friend-bsky-social"


def test_allowlist_none_allows_all():
    """When allowlist is None (legacy), all handles get facets."""
    text = "@alice.bsky.social and @bob.bsky.social"
    client = _make_client()

    facets = parse_mentions(text, client, allowed_handles=None)

    assert len(facets) == 2


def test_allowlist_empty_blocks_all():
    """Empty allowlist means no one gets tagged."""
    text = "@alice.bsky.social"
    client = _make_client()

    facets = parse_mentions(text, client, allowed_handles=set())

    assert len(facets) == 0


def test_allowlist_preserves_byte_positions():
    """Allowed mentions should still have correct byte offsets."""
    text = "hey @owner.handle check this"
    client = _make_client()

    facets = parse_mentions(text, client, allowed_handles={"owner.handle"})

    assert len(facets) == 1
    start = facets[0]["index"]["byteStart"]
    end = facets[0]["index"]["byteEnd"]
    assert text.encode("UTF-8")[start:end] == b"@owner.handle"


# regression (2026-10-20): phi replied in bufo.uk's thread with
# "@jev.zzstoatzz.io top 10 movies all time?". jev had posted in that thread,
# but only the parent's author reached the allowlist, so the tag went out as
# plain text and `post` said "published" with no hint of it.


async def test_thread_participants_cover_everyone_who_posted(monkeypatch):
    from bot.tools import posting

    def _post(handle):
        return SimpleNamespace(author=SimpleNamespace(handle=handle), indexed_at="")

    thread = SimpleNamespace(
        post=_post("bufo.uk"),
        parent=None,
        replies=[
            SimpleNamespace(
                post=_post("jev.zzstoatzz.io"),
                replies=[SimpleNamespace(post=_post("phi.zzstoatzz.io"), replies=[])],
            )
        ],
    )

    async def get_thread(uri, depth=10):
        return SimpleNamespace(thread=thread)

    monkeypatch.setattr(posting.bot_client, "get_thread", get_thread)
    assert await posting._thread_participants("at://root", "at://root") == {
        "bufo.uk",
        "jev.zzstoatzz.io",
        "phi.zzstoatzz.io",
    }


def test_untagged_mentions_are_named():
    from bot.tools.posting import _untagged_note

    note = _untagged_note("@jev.zzstoatzz.io and @bufo.uk top 10?", allowed={"bufo.uk"})
    assert "@jev.zzstoatzz.io" in note
    assert "@bufo.uk" not in note
    assert _untagged_note("@bufo.uk hi", allowed={"bufo.uk"}) == ""
