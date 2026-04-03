"""Thread utilities for ATProto thread operations."""

from collections.abc import Callable
from typing import Any


def resolve_facet_links(record) -> str:
    """Return post text with truncated link display text replaced by actual URIs from facets.

    Bluesky truncates long URLs in the display text (e.g. "example.com/long-path..."
    but stores the full URI in the facet. This walks facets right-to-left and splices
    the real URI back into the text so downstream consumers see the full link.
    """
    text = getattr(record, "text", "") or ""
    facets = getattr(record, "facets", None)
    if not facets:
        return text

    # collect link facets with byte ranges
    link_facets = []
    for facet in facets:
        index = getattr(facet, "index", None)
        features = getattr(facet, "features", None) or []
        if not index:
            continue
        for feature in features:
            py_type = getattr(feature, "py_type", "")
            if "link" in py_type:
                uri = getattr(feature, "uri", "")
                if uri:
                    link_facets.append(
                        (
                            getattr(index, "byte_start", 0),
                            getattr(index, "byte_end", 0),
                            uri,
                        )
                    )

    if not link_facets:
        return text

    # sort by byte_start descending so replacements don't shift earlier offsets
    link_facets.sort(key=lambda x: x[0], reverse=True)

    encoded = text.encode("utf-8")
    for start, end, uri in link_facets:
        encoded = encoded[:start] + uri.encode("utf-8") + encoded[end:]

    return encoded.decode("utf-8")


def describe_embed(embed) -> str | None:
    """Extract a human-readable description from a post embed.

    Handles images (with alt text), external links, quote posts,
    and record-with-media (quote + images).
    """
    if embed is None:
        return None

    parts: list[str] = []
    py_type = getattr(embed, "py_type", "")

    # images
    if "images" in py_type:
        for img in getattr(embed, "images", []):
            alt = getattr(img, "alt", "").strip()
            if alt:
                parts.append(f"[image: {alt}]")
            else:
                parts.append("[image: no alt text]")

    # external link card
    elif "external" in py_type:
        ext = getattr(embed, "external", None)
        if ext:
            title = getattr(ext, "title", "")
            desc = getattr(ext, "description", "")
            uri = getattr(ext, "uri", "")
            link_parts = []
            if title:
                link_parts.append(title)
            if desc:
                link_parts.append(desc)
            if uri:
                link_parts.append(uri)
            parts.append(f"[link: {' — '.join(link_parts)}]")

    # quote post
    elif py_type == "app.bsky.embed.record#view":
        rec = getattr(embed, "record", None)
        if rec and hasattr(rec, "value"):
            author = getattr(rec, "author", None)
            handle = getattr(author, "handle", "?") if author else "?"
            text = getattr(rec.value, "text", "")
            # Recursively describe embeds on the quoted post
            quoted_embeds = getattr(rec, "embeds", None)
            inner = ""
            if quoted_embeds:
                inner_parts = [describe_embed(e) for e in quoted_embeds]
                inner = " ".join(p for p in inner_parts if p)
            quote_content = text
            if inner:
                quote_content = f"{text} {inner}" if text else inner
            parts.append(f"[quoting @{handle}: {quote_content}]")

    # record with media (quote post + images/video)
    elif "record_with_media" in py_type:
        media = getattr(embed, "media", None)
        if media:
            media_desc = describe_embed(media)
            if media_desc:
                parts.append(media_desc)
        rec = getattr(embed, "record", None)
        if rec:
            rec_desc = describe_embed(rec)
            if rec_desc:
                parts.append(rec_desc)

    # video
    elif "video" in py_type:
        alt = getattr(embed, "alt", "")
        if alt:
            parts.append(f"[video: {alt}]")
        else:
            parts.append("[video]")

    return " ".join(parts) if parts else None


def extract_image_urls(embed) -> list[str]:
    """Extract fullsize image URLs from a post embed.

    Returns URLs that can be passed as ImageUrl to a multimodal model.
    """
    if embed is None:
        return []

    urls: list[str] = []
    py_type = getattr(embed, "py_type", "")

    if "images" in py_type:
        for img in getattr(embed, "images", []):
            fullsize = getattr(img, "fullsize", None)
            if fullsize:
                urls.append(fullsize)

    elif "record_with_media" in py_type:
        media = getattr(embed, "media", None)
        if media:
            urls.extend(extract_image_urls(media))

    return urls


def describe_post(post) -> str:
    """Build a full text representation of a post including embeds."""
    handle = post.author.handle
    text = resolve_facet_links(post.record) if hasattr(post.record, "text") else ""

    # Check for embeds on the post view (post.embed) or record (post.record.embed)
    embed_desc = None
    if hasattr(post, "embed") and post.embed:
        embed_desc = describe_embed(post.embed)
    elif hasattr(post.record, "embed") and post.record.embed:
        embed_desc = describe_embed(post.record.embed)

    if embed_desc:
        return (
            f"@{handle}: {text}\n  {embed_desc}" if text else f"@{handle}: {embed_desc}"
        )
    return f"@{handle}: {text}" if text else f"@{handle}: [no text]"


def traverse_thread(
    thread_node,
    visit: Callable[[Any], None],
    *,
    include_parent: bool = True,
    include_replies: bool = True,
):
    """Recursively traverse a thread structure and call visit() on each post.

    Args:
        thread_node: ATProto thread node with optional .post, .parent, .replies
        visit: Callback function called for each post node
        include_parent: Whether to traverse up to parent posts
        include_replies: Whether to traverse down to reply posts

    Example:
        posts = []
        traverse_thread(thread_data.thread, lambda node: posts.append(node.post))
    """
    if not thread_node or not hasattr(thread_node, "post"):
        return

    # Visit this node
    visit(thread_node)

    # Traverse parent chain (moving up the thread)
    if include_parent and hasattr(thread_node, "parent") and thread_node.parent:
        traverse_thread(
            thread_node.parent, visit, include_parent=True, include_replies=False
        )

    # Traverse replies (moving down the thread)
    if include_replies and hasattr(thread_node, "replies") and thread_node.replies:
        for reply in thread_node.replies:
            traverse_thread(reply, visit, include_parent=False, include_replies=True)


def extract_posts_chronological(thread_node) -> list[Any]:
    """Extract all posts from a thread in chronological order.

    Args:
        thread_node: ATProto thread node

    Returns:
        List of post objects sorted by timestamp
    """
    posts = []

    def collect(node):
        if hasattr(node, "post"):
            posts.append(node.post)

    traverse_thread(thread_node, collect)

    # Sort by indexed timestamp
    posts.sort(key=lambda p: p.indexed_at if hasattr(p, "indexed_at") else "")
    return posts


def build_thread_context(thread_node) -> str:
    """Build conversational context string from ATProto thread structure.

    Args:
        thread_node: ATProto thread node

    Returns:
        Formatted string of messages like:
        @alice: I love birds
        @phi: me too! what's your favorite?
        @alice: especially crows

    Example:
        thread_data = await client.get_thread(uri, depth=100)
        context = build_thread_context(thread_data.thread)
    """
    if not thread_node:
        return "No previous messages in this thread."

    posts = extract_posts_chronological(thread_node)

    if not posts:
        return "No previous messages in this thread."

    messages = [describe_post(post) for post in posts]
    return "\n".join(messages)
