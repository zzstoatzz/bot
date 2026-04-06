"""Bluesky account tools — posting, own posts, URL checks, labels, infra."""

import asyncio
import ipaddress
import socket
from datetime import date
from urllib.parse import urlparse

import httpx
from pydantic_ai import RunContext

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.mentionable import add_handle, get_mentionable_handles, remove_handle
from bot.tools._helpers import PhiDeps, _check_services_impl, _is_owner, _relative_age


def register(agent):
    @agent.tool
    async def post(ctx: RunContext[PhiDeps], text: str) -> str:
        """Create a new top-level post on Bluesky (not a reply). Use this when you want to share something with your followers unprompted."""
        try:
            allowed = {settings.owner_handle, settings.bluesky_handle}
            allowed.update(await get_mentionable_handles())
            if ctx.deps.author_handle:
                allowed.add(ctx.deps.author_handle)
            await bot_client.create_post(text, allowed_handles=allowed)
            return f"posted: {text[:100]}"
        except Exception as e:
            return f"failed to post: {e}"

    @agent.tool
    async def get_own_posts(ctx: RunContext[PhiDeps], limit: int = 10) -> str:
        """Read your own recent top-level posts (no replies). Use this instead of list_records when you need to review what you've posted."""
        try:
            posts = await bot_client.get_own_posts(limit=limit)
            if not posts:
                return "no posts found"
            today = date.today()
            lines = []
            for item in posts:
                p = item.post
                text = p.record.text if hasattr(p.record, "text") else ""
                age = (
                    _relative_age(p.indexed_at, today)
                    if hasattr(p, "indexed_at") and p.indexed_at
                    else ""
                )
                age_str = f" ({age})" if age else ""
                lines.append(f"[{p.uri}]{age_str}: {text[:200]}")
            return "\n\n".join(lines)
        except Exception as e:
            return f"failed to get own posts: {e}"

    @agent.tool
    async def check_urls(ctx: RunContext[PhiDeps], urls: list[str]) -> str:
        """Check whether URLs are reachable. Use this before sharing links to verify they actually work. Accepts full URLs (https://...) or bare domains (example.com/path)."""

        async def _check(client: httpx.AsyncClient, url: str) -> str:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            try:
                hostname = urlparse(url).hostname
                if not hostname:
                    return f"{url} → blocked: no hostname"
                # resolve and check for private/loopback IPs (SSRF protection)
                try:
                    addrs = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: socket.getaddrinfo(hostname, None)
                    )
                except socket.gaierror:
                    return f"{url} → blocked: DNS resolution failed"
                for addr_info in addrs:
                    ip = ipaddress.ip_address(addr_info[4][0])
                    if ip.is_private or ip.is_loopback or ip.is_link_local:
                        return f"{url} → blocked: private IP"

                r = await client.head(url, follow_redirects=True)
                return f"{url} → {r.status_code}"
            except httpx.TimeoutException:
                return f"{url} → timeout"
            except Exception as e:
                return f"{url} → error: {type(e).__name__}"

        async with httpx.AsyncClient(timeout=10) as client:
            results = await asyncio.gather(*[_check(client, u) for u in urls])
        return "\n".join(results)

    @agent.tool
    async def manage_labels(
        ctx: RunContext[PhiDeps], action: str, label: str = ""
    ) -> str:
        """Manage self-labels on your profile. Actions: 'list' to see current labels, 'add' to add a label, 'remove' to remove a label. The 'bot' label marks you as an automated account."""
        from bot.core.profile_manager import (
            add_self_label,
            get_self_labels,
            remove_self_label,
        )

        if action == "list":
            labels = get_self_labels(bot_client.client)
            return f"current self-labels: {labels}" if labels else "no self-labels set"
        elif action == "add":
            if not label:
                return "provide a label value to add"
            labels = add_self_label(bot_client.client, label)
            return f"added '{label}', labels now: {labels}"
        elif action == "remove":
            if not label:
                return "provide a label value to remove"
            labels = remove_self_label(bot_client.client, label)
            return f"removed '{label}', labels now: {labels}"
        else:
            return f"unknown action '{action}', use 'list', 'add', or 'remove'"

    @agent.tool
    async def manage_mentionable(
        ctx: RunContext[PhiDeps], action: str, handle: str = ""
    ) -> str:
        """Manage the list of people who have opted in to being @mentioned by you.
        OWNER-ONLY (restricted to @{settings.owner_handle}).

        Actions: 'list' to see who's opted in, 'add' to add a handle, 'remove' to remove one.

        When someone tells you "you can tag me" or similar, ask nate to confirm
        before adding them. Never add someone without operator approval."""
        if not _is_owner(ctx):
            return f"only @{settings.owner_handle} can manage the mentionable list"
        if action == "list":
            handles = await get_mentionable_handles()
            if handles:
                return f"opted-in handles: {', '.join(sorted(handles))}"
            return "no one has opted in yet"
        elif action == "add":
            if not handle:
                return "provide a handle to add"
            handles = await add_handle(handle)
            return (
                f"added @{handle} — opted-in list is now: {', '.join(sorted(handles))}"
            )
        elif action == "remove":
            if not handle:
                return "provide a handle to remove"
            handles = await remove_handle(handle)
            return f"removed @{handle} — opted-in list is now: {', '.join(sorted(handles)) or '(empty)'}"
        else:
            return f"unknown action '{action}', use 'list', 'add', or 'remove'"

    @agent.tool
    async def check_services(ctx: RunContext[PhiDeps]) -> str:
        """Check health of nate's infrastructure (plyr, PDS, prefect, etc) — NOT your own status.
        Do NOT call this when someone asks if you're online — that's about you, not infrastructure.
        Only use during daily reflection or when someone explicitly asks about services/infrastructure."""
        return await _check_services_impl()
