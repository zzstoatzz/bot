"""Thread utilities for ATProto thread operations."""

from collections.abc import Callable


def traverse_thread(
    thread_node,
    visit: Callable[[any], None],
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
        traverse_thread(thread_node.parent, visit, include_parent=True, include_replies=False)

    # Traverse replies (moving down the thread)
    if include_replies and hasattr(thread_node, "replies") and thread_node.replies:
        for reply in thread_node.replies:
            traverse_thread(reply, visit, include_parent=False, include_replies=True)


def extract_posts_chronological(thread_node) -> list[any]:
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

    messages = []
    for post in posts:
        handle = post.author.handle
        text = post.record.text if hasattr(post.record, "text") else "[no text]"
        messages.append(f"@{handle}: {text}")

    return "\n".join(messages)
