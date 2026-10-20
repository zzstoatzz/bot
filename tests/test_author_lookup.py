"""regression (2026-10-20): bufo.uk asked jev "top 10 movies all time?" and
jev answered. The question reached phi only as a bare line in the stranger
lookup, with no address and no sign of a reply, so she asked bufo what jev
said and then asked jev the question again."""

from types import SimpleNamespace

from bot.utils.lookup import fetch_author_lookup

QUESTION = "at://did:plc:bufo/app.bsky.feed.post/3myc3itudqk2e"


def _client(feed):
    async def authenticate():
        return None

    bsky = SimpleNamespace(
        actor=SimpleNamespace(
            get_profile=lambda params: SimpleNamespace(
                description="first resident of https://pds.zat.dev",
                followers_count=10,
                follows_count=4,
                posts_count=48,
                created_at="2026-05-21T00:00:00Z",
            )
        ),
        feed=SimpleNamespace(get_author_feed=lambda params: SimpleNamespace(feed=feed)),
    )
    return SimpleNamespace(
        authenticate=authenticate,
        client=SimpleNamespace(app=SimpleNamespace(bsky=bsky)),
    )


def _item(uri, text, replies):
    return SimpleNamespace(
        post=SimpleNamespace(
            uri=uri,
            record=SimpleNamespace(text=text),
            indexed_at="2026-10-20T07:13:40Z",
            reply_count=replies,
        )
    )


async def test_recent_posts_carry_their_address_and_replies():
    block = await fetch_author_lookup(
        _client(
            [
                _item(QUESTION, "@jev.zzstoatzz.io top 10 movies all time?", 1),
                _item("at://did:plc:bufo/app.bsky.feed.post/3hi", "hi", 0),
            ]
        ),
        "bufo.uk",
    )

    assert block is not None
    assert f"top 10 movies all time? [{QUESTION}] (1 reply)" in block
    assert "hi [at://did:plc:bufo/app.bsky.feed.post/3hi]\n" in block
