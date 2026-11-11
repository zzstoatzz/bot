"""Bluesky account tools — posting, own posts, URL checks, labels, infra."""

import asyncio
import ipaddress
import logging
import socket
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlparse

import httpx
from pydantic import Field
from pydantic_ai import RunContext

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.mentionable import add_handle, get_mentionable_handles, remove_handle
from bot.core.override import get_override, refusal_text
from bot.tools._helpers import PhiDeps, _check_services_impl, _is_owner, _relative_age
from bot.utils.thread import post_line

logger = logging.getLogger("bot.tools")


def _is_github_rate_limit(exc: Exception) -> bool:
    """GitHub answers an exhausted quota with 403 or 429 plus a marker header."""
    r = getattr(exc, "response", None)
    if r is None or r.status_code not in (403, 429):
        return False
    return (
        r.headers.get("x-ratelimit-remaining") == "0" or "rate limit" in r.text.lower()
    )


# A commit message carries its reasoning in the body, so the body has to
# survive — but phi's own messages run long, and a hundred of them would
# crowd out everything else in her context.
COMMIT_BODY_LIMIT = 1400
CHANGELOG_CHAR_BUDGET = 24000

def register(agent):
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
                age = _relative_age(p.indexed_at, today) if p.indexed_at else ""
                lines.append(post_line(p, extras=[age], limit=200))
            return "\n\n".join(lines)
        except Exception as e:
            return f"failed to get own posts: {e}"

    @agent.tool
    async def get_own_likes(ctx: RunContext[PhiDeps], limit: int = 25) -> str:
        """Read back the posts you've liked, newest first. Your likes are a public record of what caught your attention — this is how you revisit it."""
        try:
            feed = await bot_client.get_own_likes(limit=limit)
            if not feed:
                return "no likes yet"
            today = date.today()
            lines = []
            for item in feed:
                p = item.post
                age = _relative_age(p.indexed_at, today) if p.indexed_at else ""
                lines.append(post_line(p, extras=[age], limit=200))
            return "\n\n".join(lines)
        except Exception as e:
            return f"failed to get likes: {e}"

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
    async def manage_account(
        ctx: RunContext[PhiDeps],
        setting: Annotated[
            Literal["labels", "mentionable", "thread"],
            Field(
                description=(
                    "thread: inspect (list), mute (add), or unmute (remove) a thread by post AT-URI. "
                    "labels: self-labels on your profile (e.g. 'bot'). "
                    "mentionable: who has opted in to being @mentioned by you "
                    "(owner-only)."
                )
            ),
        ],
        action: Annotated[
            Literal["list", "add", "remove"],
            Field(description="list current values, add one, or remove one"),
        ],
        value: Annotated[
            str,
            Field(description="Label, handle, or [thread: all actions] post AT-URI"),
        ] = "",
    ) -> str:
        """Manage thread mutes, profile self-labels, or the mention opt-in list.

        Thread mutes are private and reversible. Use any post AT-URI in the
        thread. Muting disengages quietly; do not send a farewell. Do not
        undo an operator-requested mute without their approval.

        The mentionable list is OWNER-ONLY — when someone tells you "you can
        tag me", ask the operator to confirm before adding them; never add
        someone without operator approval.
        """
        if setting == "thread":
            try:
                root, muted = await bot_client.thread_mute_state(value)
                if action != "list":
                    desired = action == "add"
                    if muted != desired:
                        graph = bot_client.client.app.bsky.graph
                        method = graph.mute_thread if desired else graph.unmute_thread
                        method({"root": root})
                    _, muted = await bot_client.thread_mute_state(root)
                    if muted != desired:
                        return "thread change could not be verified; inspect before retrying"
                return f"thread: {root}\nmuted: {muted}"
            except Exception as error:
                return f"thread operation failed: {error}"

        if action != "list":
            override = await get_override()
            if override["active"]:
                return refusal_text(override)

        if setting == "labels":
            from bot.core.profile_manager import (
                add_self_label,
                get_self_labels,
                remove_self_label,
            )

            if action == "list":
                labels = get_self_labels(bot_client.client)
                return (
                    f"current self-labels: {labels}" if labels else "no self-labels set"
                )
            if not value:
                return f"provide a label value to {action}"
            if action == "add":
                labels = add_self_label(bot_client.client, value)
                return f"added '{value}', labels now: {labels}"
            labels = remove_self_label(bot_client.client, value)
            return f"removed '{value}', labels now: {labels}"

        if not _is_owner(ctx):
            return f"only @{settings.owner_handle} can manage the mentionable list"
        if action == "list":
            handles = await get_mentionable_handles()
            if handles:
                return f"opted-in handles: {', '.join(sorted(handles))}"
            return "no one has opted in yet"
        if not value:
            return f"provide a handle to {action}"
        if action == "add":
            handles = await add_handle(value)
            return (
                f"added @{value} — opted-in list is now: {', '.join(sorted(handles))}"
            )
        handles = await remove_handle(value)
        return f"removed @{value} — opted-in list is now: {', '.join(sorted(handles)) or '(empty)'}"

    @agent.tool
    async def check_infra(
        ctx: RunContext[PhiDeps],
        aspect: Annotated[
            Literal["services", "changelog"],
            Field(
                description=(
                    "services: health of the operator's apps (plyr, PDS, "
                    "prefect, ...). changelog: your own development "
                    "history — commits with their full messages, which is "
                    "where the reasoning for a change lives, not just what "
                    "changed. windowable with since/until and count."
                )
            ),
        ] = "services",
        count: Annotated[
            int,
            Field(
                description=(
                    "[changelog] how many commits to return (max 100). pair "
                    "with since/until to walk backwards through history a "
                    "window at a time rather than asking for everything."
                )
            ),
        ] = 10,
        since: Annotated[
            str | None,
            Field(
                description=(
                    "[changelog] start of window, ISO 8601 UTC (e.g. "
                    "'2026-04-16T00:00:00Z'), to read an earlier period of "
                    "your own development."
                )
            ),
        ] = None,
        until: Annotated[
            str | None,
            Field(description="End of window, ISO 8601 UTC. Pairs with since."),
        ] = None,
    ) -> str:
        """Read app health or bot commits. Relay coverage is the relay_eval tool.

        services: health of the operator's apps; this does not check Phi's status.
        It is a read from outside, through each app's public address, at one
        moment. You cannot restart, deploy, or log in to anything it checks;
        what you can do is tell the operator what you read and when. prefect,
        grafana and the hub routes share one tunnel from the operator's home
        machine: a 530 on them together means that tunnel is disconnected, and
        they return together when it reconnects. A duration needs readings
        that span it; two failed reads days apart are two failed reads.
        changelog: bot commits and full messages from the GitHub mirror. Bound
        the result with count and since/until.
        """
        if aspect == "services":
            return await _check_services_impl()

        if aspect == "changelog":
            # Full commit messages, not just subjects. The subject says what
            # changed; the body says why, and the why is the part that is
            # not reconstructable from the diff. Each message is truncated
            # individually and the whole response is bounded, so a wide
            # window degrades into "narrow it" rather than flooding context.
            params: dict[str, str | int] = {"per_page": max(1, min(count, 100))}
            if since:
                params["since"] = since
            if until:
                params["until"] = until
            # unauthenticated this endpoint allows 60 requests/hour per IP,
            # which a single busy run can exhaust — send the token when there
            # is one (5,000/hour) and degrade rather than fail without it.
            headers = {"Accept": "application/vnd.github+json"}
            if settings.github_token:
                headers["Authorization"] = f"Bearer {settings.github_token}"
            try:
                async with httpx.AsyncClient(timeout=15) as http:
                    r = await http.get(
                        "https://api.github.com/repos/zzstoatzz/bot/commits",
                        params=params,
                        headers=headers,
                    )
                    r.raise_for_status()
                    commits = r.json()
            except Exception as e:
                if _is_github_rate_limit(e):
                    logger.warning(f"changelog hit the github rate limit: {e}")
                    return (
                        "changelog unavailable: github rate limit. this call is "
                        + (
                            "authenticated"
                            if settings.github_token
                            else "unauthenticated"
                        )
                        + ", so the ceiling is "
                        + ("5,000" if settings.github_token else "60")
                        + "/hour. retry later or narrow the window."
                    )
                logger.warning(f"failed to fetch changelog: {e}")
                return f"failed to fetch changelog: {e}"

            if not commits:
                return (
                    "no commits in that window. the repo starts 2025-07; "
                    "widen since/until."
                )

            entries: list[str] = []
            total = 0
            for c in commits:
                when = c["commit"]["author"]["date"][:10]
                sha = c["sha"][:8]
                message = c["commit"]["message"].strip()
                if len(message) > COMMIT_BODY_LIMIT:
                    message = message[: COMMIT_BODY_LIMIT - 1].rstrip() + "…"
                entry = f"[{when} {sha}] {message}"
                if total + len(entry) > CHANGELOG_CHAR_BUDGET:
                    entries.append(
                        f"… stopped at {len(entries)} of {len(commits)} commits "
                        "(response budget). narrow the window with since/until."
                    )
                    break
                entries.append(entry)
                total += len(entry)
            return "\n\n".join(entries)

        raise AssertionError(f"unhandled aspect {aspect}")

