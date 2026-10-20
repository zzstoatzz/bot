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


def _field(obj, name: str, default=None):
    """``obj.name`` on an atproto model, ``obj[name]`` or its camelCase on appview JSON."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        camel = name.split("_")[0] + "".join(w.title() for w in name.split("_")[1:])
        value = obj.get(name, obj.get(camel))
    else:
        value = getattr(obj, name, None)
    return default if value is None else value


def _plural(n: int, word: str) -> str:
    if n == 1:
        return f"{n} {word}"
    return f"{n} {word[:-1]}ies" if word.endswith("y") else f"{n} {word}s"


def engagement(post) -> str:
    """``"3 replies, 1 quote"`` for a post view, or ``""`` when nobody answered it."""
    parts = []
    if replies := _field(post, "reply_count", 0):
        parts.append(_plural(replies, "reply"))
    if quotes := _field(post, "quote_count", 0):
        parts.append(_plural(quotes, "quote"))
    return ", ".join(parts)


def post_text(post) -> str:
    record = _field(post, "record")
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("text", "") or ""
    return resolve_facet_links(record) if hasattr(record, "text") else ""


def post_line(
    post, *, extras: list[str] | None = None, limit: int | None = None
) -> str:
    """The one way a post is shown: ``@handle [at-uri] (N replies, M quotes): text``.

    Every surface used to render posts its own way, and most dropped the uri
    or the reply count, so phi saw a post with no way to open it and no sign
    anyone had answered it (asked "what did it say to the movies question?"
    about a reply it could have read, 2026-10-20). Takes atproto views or
    appview JSON. ``extras`` (likes, age) go inside the parentheses.
    """
    handle = _field(_field(post, "author"), "handle", "?")
    uri = _field(post, "uri", "")
    text = post_text(post)
    if limit and len(text) > limit:
        text = text[: limit - 1] + "…"
    meta = ", ".join(p for p in [engagement(post), *(extras or [])] if p)
    head = f"@{handle} [{uri}]" + (f" ({meta})" if meta else "")

    embed_desc = None
    if not isinstance(post, dict):
        embed = _field(post, "embed") or _field(_field(post, "record"), "embed")
        embed_desc = describe_embed(embed) if embed else None
    if embed_desc:
        return f"{head}: {text}\n  {embed_desc}" if text else f"{head}: {embed_desc}"
    return f"{head}: {text}" if text else f"{head}: [no text]"


def describe_post(post) -> str:
    """Build a full text representation of a post including embeds."""
    return post_line(post)


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


def _loaded_replies(node) -> list:
    replies = [r for r in (_field(node, "replies") or []) if _field(r, "post")]
    return sorted(replies, key=lambda r: _field(_field(r, "post"), "indexed_at", ""))


def render_thread(thread_node, *, indent: str = "  ") -> str:
    """A thread as phi reads it: the parent chain, then each reply nested under
    the post it answers, with a marker wherever replies exist but weren't loaded.

    The flat chronological list this replaced lost who was answering whom and
    gave no sign that a branch went deeper than the fetch. Same shape as the
    read-thread skill's output, so a thread looks the same however phi got it.
    """
    if not thread_node or not _field(thread_node, "post"):
        return "No previous messages in this thread."

    ancestors = []
    parent = _field(thread_node, "parent")
    while parent is not None and _field(parent, "post"):
        ancestors.append(parent)
        parent = _field(parent, "parent")
    lines = [post_line(_field(a, "post")) for a in reversed(ancestors)]

    def walk(node, depth: int) -> None:
        pad = indent * depth
        post = _field(node, "post")
        lines.append(pad + post_line(post).replace("\n", "\n" + pad))
        replies = _loaded_replies(node)
        for reply in replies:
            walk(reply, depth + 1)
        if (missing := _field(post, "reply_count", 0) - len(replies)) > 0:
            lines.append(
                f"{pad}{indent}… {_plural(missing, 'more reply')}"
                f" below, read-thread from [{_field(post, 'uri', '')}]"
            )

    walk(thread_node, 0)
    return "\n".join(lines)


def build_thread_context(thread_node) -> str:
    """Conversational context for a notification: see :func:`render_thread`."""
    return render_thread(thread_node)


def thread_root_view(thread_node, root_uri: str) -> tuple[str, str]:
    """``(author_handle, text)`` of the thread's root post, or ``("", "")``.

    The root is the post whose uri is ``root_uri``; when the fetched thread
    does not reach it, the earliest post stands in. A reply's context used
    to be a flat list where the root was only the first line — nothing
    said whose thread it was, which is the first thing a person tagged into
    a thread looks at (the marble-cake replies, 2026-09-02).
    """
    posts = extract_posts_chronological(thread_node) if thread_node else []
    if not posts:
        return "", ""
    root = next((p for p in posts if getattr(p, "uri", "") == root_uri), posts[0])
    handle = getattr(getattr(root, "author", None), "handle", "") or ""
    record = getattr(root, "record", None)
    text = (
        resolve_facet_links(record)
        if record is not None and hasattr(record, "text")
        else ""
    )
    return handle, text


def thread_has(thread_node, uri: str) -> bool:
    found = False

    def visit(node):
        nonlocal found
        found = found or getattr(getattr(node, "post", None), "uri", "") == uri

    traverse_thread(thread_node, visit)
    return found


async def fetch_thread_context(view, root_uri: str, post_uri: str):
    """``(context, root_node)`` for a post: the thread from its root, plus the
    branch down to the post when the root fetch stops above it.

    The appview stops 10 levels below whatever post a thread is fetched from,
    whatever depth is asked for. Fetched only from the root, a deep reply and
    everything near it vanished without a marker: phi was asked to fix her
    own post in bufo.uk's thread and never saw it (2026-10-20).
    """
    root = (await view.get_thread(root_uri, depth=100)).thread
    context = render_thread(root)
    if post_uri != root_uri and not thread_has(root, post_uri):
        branch = (await view.get_thread(post_uri, depth=6)).thread
        context += (
            "\n\nthe branch down to this post, below where the view above stops:\n"
            + render_thread(branch)
        )
    return context, root
