"""Platform-neutral incoming messages: what someone said and what came with it.

A message is text plus the things attached to it. Each surface (Bluesky DMs
today, notifications and other channels later) gets one adapter that turns its
native shape into `InboundMessage`; the agent reads the neutral shape and never
has to know which surface's embed or facet format the content arrived in.

The shape borrows from Letta's channel model (text, verified mentions,
attachments, reply context) and adds `references`, because on atproto most of
what rides along with a message is a pointer to another record or page, not a
file.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

from bot.utils.thread import resolve_facet_links


@dataclass
class Mention:
    """A participant the platform verified, not a guess from @text."""

    did: str
    text: str


@dataclass
class Reference:
    """Something the message points at: a post, a link card, another record."""

    kind: Literal["post", "link", "record", "unavailable"]
    uri: str = ""
    author_handle: str = ""
    author_did: str = ""
    text: str = ""
    title: str = ""


@dataclass
class Attachment:
    """Media carried by the message itself."""

    kind: Literal["image", "video", "file"]
    alt: str = ""
    url: str = ""


@dataclass
class InboundMessage:
    channel: str
    id: str
    author: str
    sent: float
    text: str
    mentions: list[Mention] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    reply_to: str = ""

    def as_material(self) -> dict:
        """Plain dict for prompt material; empty extras are omitted."""
        out = {k: v for k, v in asdict(self).items() if v not in ("", [], None)}
        out["text"] = self.text
        return out


# --- bluesky chat (chat.bsky.convo) -----------------------------------------


def _mentions(record) -> list[Mention]:
    text = (getattr(record, "text", "") or "").encode("utf-8")
    found = []
    for facet in getattr(record, "facets", None) or []:
        index = getattr(facet, "index", None)
        for feature in getattr(facet, "features", None) or []:
            did = getattr(feature, "did", None)
            if (
                index is not None
                and did
                and "mention" in (getattr(feature, "py_type", "") or "")
            ):
                span = text[index.byte_start : index.byte_end]
                found.append(Mention(did=did, text=span.decode("utf-8", "replace")))
    return found


def _record_reference(view) -> Reference:
    """One app.bsky.embed.record view record, hydrated by the appview."""
    py_type = getattr(view, "py_type", "") or ""
    uri = getattr(view, "uri", "") or ""
    if not py_type.endswith("#viewRecord"):
        # notFound / blocked / detached, or a feed, list, starter pack view
        title = getattr(view, "display_name", None) or getattr(view, "name", "")
        kind = "record" if title else "unavailable"
        return Reference(kind=kind, uri=uri, title=title or "")
    author = getattr(view, "author", None)
    value = getattr(view, "value", None)
    text = resolve_facet_links(value) if value is not None else ""
    is_post = "/app.bsky.feed.post/" in uri
    return Reference(
        kind="post" if is_post else "record",
        uri=uri,
        author_handle=getattr(author, "handle", "") or "",
        author_did=getattr(author, "did", "") or "",
        text=text,
    )


def _embed_parts(embed) -> tuple[list[Reference], list[Attachment]]:
    if embed is None:
        return [], []
    py_type = getattr(embed, "py_type", "") or ""
    if py_type.startswith("app.bsky.embed.recordWithMedia"):
        refs, _ = _embed_parts(getattr(embed, "record", None))
        _, media = _embed_parts(getattr(embed, "media", None))
        return refs, media
    if py_type.startswith("app.bsky.embed.record"):
        return [_record_reference(getattr(embed, "record", None))], []
    if py_type.startswith("app.bsky.embed.external"):
        ext = getattr(embed, "external", None)
        return [
            Reference(
                kind="link",
                uri=getattr(ext, "uri", "") or "",
                title=getattr(ext, "title", "") or "",
                text=getattr(ext, "description", "") or "",
            )
        ], []
    if py_type.startswith("app.bsky.embed.images"):
        return [], [
            Attachment(
                kind="image",
                alt=getattr(image, "alt", "") or "",
                url=getattr(image, "fullsize", "") or "",
            )
            for image in getattr(embed, "images", None) or []
        ]
    if py_type.startswith("app.bsky.embed.video"):
        return [], [Attachment(kind="video", alt=getattr(embed, "alt", "") or "")]
    return [], []


def from_bsky_chat(message) -> InboundMessage | None:
    """A chat.bsky.convo messageView, or None for deleted/system messages.

    A shared post arrives as a message with empty text and a record embed, so
    an empty `text` is not an empty message.
    """
    sender = getattr(message, "sender", None)
    sent_at = getattr(message, "sent_at", None)
    if sender is None or not sent_at:
        return None
    references, attachments = _embed_parts(getattr(message, "embed", None))
    text = resolve_facet_links(message)
    if not text and not references and not attachments:
        return None
    reply = getattr(message, "reply_to", None)
    return InboundMessage(
        channel="bluesky-dm",
        id=message.id,
        author=sender.did,
        sent=datetime.fromisoformat(sent_at.replace("Z", "+00:00")).timestamp(),
        text=text,
        mentions=_mentions(message),
        references=references,
        attachments=attachments,
        reply_to=getattr(reply, "id", "") or "",
    )
