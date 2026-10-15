"""Bluesky DM messages keep what rode along with the text."""

from atproto import models

from bot.core import operator_reports as reports
from bot.core.inbound import _embed_parts, from_bsky_chat

SENT = "2026-10-15T15:00:00.000Z"
ASTRA = "did:plc:astra"
POST = f"at://{ASTRA}/app.bsky.feed.post/3abc"


def _message(**fields):
    return models.ChatBskyConvoDefs.MessageView(
        id=fields.pop("id", "m1"),
        rev="r",
        sender=models.ChatBskyConvoDefs.MessageViewSender(did="did:plc:nate"),
        sent_at=SENT,
        text=fields.pop("text", ""),
        **fields,
    )


def _inbound(message):
    inbound = from_bsky_chat(message)
    assert inbound is not None
    return inbound


def _shared_post():
    return models.AppBskyEmbedRecord.View(
        record=models.AppBskyEmbedRecord.ViewRecord(
            uri=POST,
            cid="bafyreib",
            indexed_at=SENT,
            author=models.AppBskyActorDefs.ProfileViewBasic(
                did=ASTRA, handle="astrra.space"
            ),
            value=models.AppBskyFeedPost.Record(
                text="question to all ai agents that read this post",
                created_at=SENT,
            ),
        )
    )


def test_shared_post_with_no_text_is_kept_with_its_author():
    inbound = _inbound(_message(embed=_shared_post()))
    assert inbound.text == ""
    [ref] = inbound.references
    assert ref.kind == "post"
    assert ref.uri == POST
    assert ref.author_handle == "astrra.space"
    assert ref.author_did == ASTRA
    assert "random" not in ref.text and "ai agents" in ref.text


def test_shared_post_reaches_the_conversation_material():
    import json

    history = [_inbound(_message(embed=_shared_post())).as_material()]
    material = json.loads(reports.conversation_material(history, ["m1"]))
    [message] = material["messages"]
    assert message["references"][0]["author_handle"] == "astrra.space"
    assert message["new_incoming"]


def test_mentions_and_truncated_links_come_from_facets():
    text = "follow @astrra.space see example.com/a..."
    encoded = text.encode()
    mention_start = encoded.index(b"@")
    link_start = encoded.index(b"example")
    facets = [
        models.AppBskyRichtextFacet.Main(
            index=models.AppBskyRichtextFacet.ByteSlice(
                byte_start=mention_start, byte_end=mention_start + 13
            ),
            features=[models.AppBskyRichtextFacet.Mention(did=ASTRA)],
        ),
        models.AppBskyRichtextFacet.Main(
            index=models.AppBskyRichtextFacet.ByteSlice(
                byte_start=link_start, byte_end=len(encoded)
            ),
            features=[
                models.AppBskyRichtextFacet.Link(uri="https://example.com/a/long")
            ],
        ),
    ]
    inbound = _inbound(_message(text=text, facets=facets))
    assert inbound.text.endswith("https://example.com/a/long")
    assert [(m.did, m.text) for m in inbound.mentions] == [(ASTRA, "@astrra.space")]


def test_link_card_and_unavailable_record():
    # DMs only carry record embeds; cards come from posts and share the parser.
    card = models.AppBskyEmbedExternal.View(
        external=models.AppBskyEmbedExternal.ViewExternal(
            uri="https://astrra.space", title="astra", description="a bot"
        )
    )
    [link], _ = _embed_parts(card)
    assert (link.kind, link.uri, link.title) == (
        "link",
        "https://astrra.space",
        "astra",
    )

    gone = models.AppBskyEmbedRecord.View(
        record=models.AppBskyEmbedRecord.ViewNotFound(uri=POST, not_found=True)
    )
    [ref] = _inbound(_message(embed=gone)).references
    assert (ref.kind, ref.uri) == ("unavailable", POST)


def test_empty_message_is_dropped():
    assert from_bsky_chat(_message()) is None
