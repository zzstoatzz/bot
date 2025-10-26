#!/usr/bin/env python3
"""View a bluesky thread with full conversation context."""

import sys
import httpx
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

console = Console()


def fetch_thread(post_uri: str):
    """Fetch thread using public API."""
    response = httpx.get(
        "https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread",
        params={"uri": post_uri, "depth": 100}
    )
    return response.json()["thread"]


def format_timestamp(iso_time: str) -> str:
    """Format ISO timestamp to readable format."""
    dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def render_post(post_data, is_phi: bool = False):
    """Render a single post."""
    post = post_data["post"]
    author = post["author"]
    record = post["record"]

    # Author and timestamp
    handle = author["handle"]
    timestamp = format_timestamp(post["indexedAt"])

    # Text content
    text = record.get("text", "[no text]")

    # Style based on author
    if is_phi or "phi.zzstoatzz.io" in handle:
        border_style = "cyan"
        title = f"[bold cyan]@{handle}[/bold cyan] [dim]{timestamp}[/dim]"
    else:
        border_style = "white"
        title = f"[bold]@{handle}[/bold] [dim]{timestamp}[/dim]"

    return Panel(
        text,
        title=title,
        border_style=border_style,
        width=100
    )


def render_thread_recursive(thread_data, indent=0):
    """Recursively render thread and replies."""
    if "post" not in thread_data:
        return

    # Render this post
    is_phi = "phi.zzstoatzz.io" in thread_data["post"]["author"]["handle"]
    panel = render_post(thread_data, is_phi=is_phi)

    # Add indentation for replies
    if indent > 0:
        console.print("  " * indent + "↳")

    console.print(panel)

    # Render replies
    if "replies" in thread_data and thread_data["replies"]:
        for reply in thread_data["replies"]:
            render_thread_recursive(reply, indent + 1)


def display_thread_linear(thread_data):
    """Display thread in linear chronological order (easier to read)."""
    posts = []

    def collect_posts(node):
        if "post" not in node:
            return
        posts.append(node)
        if "replies" in node and node["replies"]:
            for reply in node["replies"]:
                collect_posts(reply)

    collect_posts(thread_data)

    # Sort by timestamp
    posts.sort(key=lambda p: p["post"]["indexedAt"])

    console.print("[bold]Thread in chronological order:[/bold]\n")

    for post_data in posts:
        post = post_data["post"]
        author = post["author"]["handle"]
        timestamp = format_timestamp(post["indexedAt"])
        text = post["record"].get("text", "[no text]")

        is_phi = "phi.zzstoatzz.io" in author

        if is_phi:
            style = "cyan"
            prefix = "🤖 phi:"
        else:
            style = "white"
            prefix = f"@{author}:"

        console.print(f"[{style}]{prefix}[/{style}] [dim]{timestamp}[/dim]")
        console.print(f"  {text}")
        console.print()


def main():
    if len(sys.argv) < 2:
        console.print("[red]Usage: python view_thread.py <post_uri_or_url>[/red]")
        console.print("\nExamples:")
        console.print("  python view_thread.py at://did:plc:abc.../app.bsky.feed.post/123")
        console.print("  python view_thread.py https://bsky.app/profile/handle/post/123")
        return

    post_uri = sys.argv[1]

    # Convert URL to URI if needed
    if post_uri.startswith("https://"):
        # Extract parts from URL
        # https://bsky.app/profile/phi.zzstoatzz.io/post/3m42jxbntr223
        parts = post_uri.split("/")
        if len(parts) >= 6:
            handle = parts[4]
            post_id = parts[6]

            # Resolve handle to DID
            response = httpx.get(
                "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle",
                params={"handle": handle}
            )
            did = response.json()["did"]
            post_uri = f"at://{did}/app.bsky.feed.post/{post_id}"

    console.print(f"[bold]Fetching thread: {post_uri}[/bold]\n")

    try:
        thread = fetch_thread(post_uri)
        display_thread_linear(thread)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
