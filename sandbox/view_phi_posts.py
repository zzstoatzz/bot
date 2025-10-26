#!/usr/bin/env python3
"""View phi's recent posts without authentication."""

import httpx
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

PHI_HANDLE = "phi.zzstoatzz.io"


def fetch_phi_posts(limit: int = 10):
    """Fetch phi's recent posts using public API."""
    # Resolve handle to DID
    response = httpx.get(
        "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle",
        params={"handle": PHI_HANDLE}
    )
    did = response.json()["did"]

    # Get author feed (public posts)
    response = httpx.get(
        "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
        params={"actor": did, "limit": limit}
    )

    return response.json()["feed"]


def format_timestamp(iso_time: str) -> str:
    """Format ISO timestamp to readable format."""
    dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
    now = datetime.now(dt.tzinfo)
    delta = now - dt

    if delta.seconds < 60:
        return f"{delta.seconds}s ago"
    elif delta.seconds < 3600:
        return f"{delta.seconds // 60}m ago"
    elif delta.seconds < 86400:
        return f"{delta.seconds // 3600}h ago"
    else:
        return f"{delta.days}d ago"


def display_posts(feed_items):
    """Display posts in a readable format."""
    for item in feed_items:
        post = item["post"]
        record = post["record"]

        # Check if this is a reply
        is_reply = "reply" in record
        reply_indicator = "↳ REPLY" if is_reply else "✓ POST"

        # Format header
        timestamp = format_timestamp(post["indexedAt"])
        header = f"[cyan]{reply_indicator}[/cyan] [dim]{timestamp}[/dim]"

        # Get post text
        text = record.get("text", "[no text]")

        # Show parent if it's a reply
        parent_text = ""
        if is_reply:
            parent_uri = record["reply"]["parent"]["uri"]
            parent_text = f"[dim]replying to: {parent_uri}[/dim]\n\n"

        # Format post
        content = Text()
        if parent_text:
            content.append(parent_text, style="dim")
        content.append(text)

        # Display
        panel = Panel(
            content,
            title=header,
            border_style="blue" if is_reply else "green",
            width=80
        )
        console.print(panel)
        console.print()


def main():
    console.print("[bold]Fetching phi's recent posts...[/bold]\n")

    try:
        feed = fetch_phi_posts(limit=10)
        display_posts(feed)
        console.print(f"[dim]Showing {len(feed)} most recent posts[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
