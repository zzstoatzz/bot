"""MCP-enabled agent for phi with structured memory."""

import asyncio
import ipaddress
import logging
import os
import socket
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ImageUrl, RunContext
from pydantic_ai.mcp import MCPServerStreamableHTTP

from bot.config import settings
from bot.memory import NamespaceMemory

logger = logging.getLogger("bot.agent")

# Operational instructions kept separate from personality — these are
# system-level guardrails that change when tools/architecture change.
OPERATIONAL_INSTRUCTIONS = """
indicate your response action via the structured output — do not use atproto tools to post, like, or repost directly.
when sharing URLs, verify them with check_urls first and always include https://.

you receive all notification types — mentions, replies, quotes, likes, reposts, and follows.
for mentions, replies, and quotes: someone is talking to you or about you. respond if you have something to say.
for likes, reposts, and follows: someone showed up. use your tools to learn about them — check their profile, read their posts, see what they're about. note anything interesting for later. you'll almost never reply to a like, but you might learn something worth remembering.
""".strip()


def _relative_age(timestamp: str, today: date) -> str:
    """Turn an ISO timestamp into a human-readable age like '2y ago' or '3d ago'."""
    try:
        post_date = date.fromisoformat(timestamp[:10])
    except (ValueError, TypeError):
        return ""
    delta = today - post_date
    days = delta.days
    if days < 0:
        return ""
    if days == 0:
        return "today"
    if days == 1:
        return "1d ago"
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    years = days // 365
    remaining_months = (days % 365) // 30
    if remaining_months:
        return f"{years}y {remaining_months}mo ago"
    return f"{years}y ago"


@dataclass
class PhiDeps:
    """Typed dependencies passed to every tool via RunContext."""

    author_handle: str
    memory: NamespaceMemory | None = None
    thread_uri: str | None = None


class Response(BaseModel):
    """Agent response indicating what action to take."""

    action: str = Field(description="reply, like, repost, or ignore")
    text: str | None = Field(default=None, description="response text when action is reply")
    reason: str | None = Field(default=None, description="brief reason when action is ignore")


def _format_user_results(results: list[dict], handle: str) -> list[str]:
    parts = []
    for r in results:
        kind = r.get("kind", "unknown")
        content = r.get("content", "")
        tags = r.get("tags", [])
        tag_str = f"[{', '.join(tags)}]" if tags else ""
        parts.append(f"[{kind}]{tag_str} {content}")
    return parts


def _format_episodic_results(results: list[dict]) -> list[str]:
    parts = []
    for r in results:
        tags = f" [{', '.join(r['tags'])}]" if r.get("tags") else ""
        parts.append(f"{r['content']}{tags}")
    return parts


def _format_unified_results(results: list[dict], handle: str) -> list[str]:
    parts = []
    for r in results:
        source = r.get("_source", "")
        content = r.get("content", "")
        tags = r.get("tags", [])
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        if source == "user":
            kind = r.get("kind", "unknown")
            parts.append(f"[@{handle} {kind}]{tag_str} {content}")
        else:
            parts.append(f"[note]{tag_str} {content}")
    return parts


class PhiAgent:
    """phi - bluesky bot with structured memory and MCP tools."""

    def __init__(self):
        # Ensure API keys from settings are in environment for libraries that check os.environ
        if settings.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        # Load personality
        personality_path = Path(settings.personality_file)
        self.base_personality = personality_path.read_text()

        # Initialize memory (TurboPuffer)
        if settings.turbopuffer_api_key and settings.openai_api_key:
            self.memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
            logger.info("memory enabled (turbopuffer)")
        else:
            self.memory = None
            logger.warning("no memory - missing turbopuffer or openai key")

        # Generic atproto record CRUD via hosted pdsx MCP
        pdsx_mcp = MCPServerStreamableHTTP(
            url="https://pdsx-by-zzstoatzz.fastmcp.app/mcp",
            timeout=30,
            headers={
                "x-atproto-handle": settings.bluesky_handle,
                "x-atproto-password": settings.bluesky_password,
            },
        )

        # ATProto publication search via hosted pub-search MCP
        pub_search_mcp = MCPServerStreamableHTTP(
            url="https://pub-search-by-zzstoatzz.fastmcp.app/mcp",
            timeout=30,
            tool_prefix="pub",
        )

        # Create PydanticAI agent with MCP tools
        self.agent = Agent[PhiDeps, Response](
            name="phi",
            model="anthropic:claude-sonnet-4-6",
            system_prompt=f"{self.base_personality}\n\n{OPERATIONAL_INSTRUCTIONS}",
            output_type=Response,
            deps_type=PhiDeps,
            toolsets=[pdsx_mcp, pub_search_mcp],
        )

        # --- memory tools ---

        @self.agent.tool
        async def recall(ctx: RunContext[PhiDeps], query: str, about: str = "") -> str:
            """Search memory. By default searches both your notes and what you know about the current user.
            Pass about="@handle" to search a specific user, or about="self" for only your own notes."""
            if not ctx.deps.memory:
                return "memory not available"

            if about == "self":
                results = await ctx.deps.memory.search_episodic(query, top_k=10)
                if not results:
                    return "no relevant memories found"
                return "\n".join(_format_episodic_results(results))

            if about.startswith("@"):
                handle = about.lstrip("@")
                results = await ctx.deps.memory.search(handle, query, top_k=10)
                if not results:
                    return f"no memories found about @{handle}"
                return "\n".join(_format_user_results(results, handle))

            if about == "":
                results = await ctx.deps.memory.search_unified(ctx.deps.author_handle, query, top_k=8)
                if not results:
                    return "no relevant memories found"
                return "\n".join(_format_unified_results(results, ctx.deps.author_handle))

            # bare handle without @
            results = await ctx.deps.memory.search(about, query, top_k=10)
            if not results:
                return f"no memories found about @{about}"
            return "\n".join(_format_user_results(results, about))

        @self.agent.tool
        async def note(ctx: RunContext[PhiDeps], content: str, tags: list[str]) -> str:
            """Leave a note for your future self. Use for facts, patterns, or corrections worth recalling later."""
            if not ctx.deps.memory:
                return "memory not available"
            await ctx.deps.memory.store_episodic_memory(content, tags, source="tool")
            return f"noted: {content[:100]}"

        @self.agent.tool
        async def search_posts(ctx: RunContext[PhiDeps], query: str, limit: int = 10) -> str:
            """Search Bluesky posts by keyword. Use this to find what people are saying about a topic."""
            from bot.core.atproto_client import bot_client

            try:
                response = bot_client.client.app.bsky.feed.search_posts(
                    params={"q": query, "limit": min(limit, 25), "sort": "top"}
                )
                if not response.posts:
                    return f"no posts found for '{query}'"

                today = date.today()
                lines = []
                for post in response.posts:
                    text = post.record.text if hasattr(post.record, "text") else ""
                    handle = post.author.handle
                    likes = post.like_count or 0
                    age = _relative_age(post.indexed_at, today) if hasattr(post, "indexed_at") and post.indexed_at else ""
                    age_str = f", {age}" if age else ""
                    lines.append(f"@{handle} ({likes} likes{age_str}): {text[:200]}")
                return "\n\n".join(lines)
            except Exception as e:
                return f"search failed: {e}"

        @self.agent.tool
        async def get_trending(ctx: RunContext[PhiDeps]) -> str:
            """Get what's currently trending on Bluesky. Returns entity-level trends from the firehose (via coral) and official Bluesky trending topics. Use this when someone asks about current events, what people are talking about, or when you want timely context."""
            parts: list[str] = []

            async with httpx.AsyncClient(timeout=15) as client:
                # coral entity graph — NER-extracted trending entities from the firehose
                try:
                    r = await client.get("https://coral.fly.dev/entity-graph")
                    r.raise_for_status()
                    data = r.json()
                    entities = data.get("entities", [])
                    stats = data.get("stats", {})

                    by_trend = sorted(
                        entities, key=lambda e: e.get("trend", 0), reverse=True
                    )[:15]

                    lines = [
                        f"coral ({stats.get('active', 0)} active entities, "
                        f"{stats.get('clusters', 0)} clusters"
                        f"{', percolating' if stats.get('percolates') else ''}):"
                    ]
                    for e in by_trend:
                        lines.append(
                            f"  {e['text']} ({e.get('label', '')}) "
                            f"trend={e.get('trend', 0):.2f}"
                        )
                    parts.append("\n".join(lines))
                except Exception as e:
                    parts.append(f"coral unavailable: {e}")

                # official bluesky trending topics
                try:
                    r = await client.get(
                        "https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrendingTopics"
                    )
                    r.raise_for_status()
                    topics = r.json().get("topics", [])
                    if topics:
                        lines = ["bluesky trending:"]
                        for t in topics[:15]:
                            lines.append(f"  {t.get('displayName', t.get('topic', ''))}")
                        parts.append("\n".join(lines))
                except Exception as e:
                    parts.append(f"bluesky trending unavailable: {e}")

            return "\n\n".join(parts) if parts else "no trending data available"

        @self.agent.tool
        async def manage_labels(
            ctx: RunContext[PhiDeps], action: str, label: str = ""
        ) -> str:
            """Manage self-labels on your profile. Actions: 'list' to see current labels, 'add' to add a label, 'remove' to remove a label. The 'bot' label marks you as an automated account."""
            from bot.core.atproto_client import bot_client
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

        @self.agent.tool
        async def post(ctx: RunContext[PhiDeps], text: str) -> str:
            """Create a new top-level post on Bluesky (not a reply). Use this when you want to share something with your followers unprompted."""
            from bot.core.atproto_client import bot_client

            try:
                result = await bot_client.create_post(text)
                return f"posted: {text[:100]}"
            except Exception as e:
                return f"failed to post: {e}"

        @self.agent.tool
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

        logger.info("phi agent initialized with pdsx + pub-search mcp tools")

    async def process_mention(
        self,
        mention_text: str,
        author_handle: str,
        thread_context: str,
        thread_uri: str | None = None,
        image_urls: list[str] | None = None,
    ) -> Response:
        """Process a mention with structured memory context."""
        # Build context from memory if available
        memory_context = ""
        episodic_context = ""
        if self.memory:
            try:
                memory_context = await self.memory.build_user_context(
                    author_handle, query_text=mention_text, include_core=True
                )
                logger.info(f"memory context for @{author_handle}: {len(memory_context)} chars")
            except Exception as e:
                logger.warning(f"failed to retrieve memories: {e}")

            try:
                episodic_context = await self.memory.get_episodic_context(mention_text)
                if episodic_context:
                    logger.info(f"episodic context: {len(episodic_context)} chars")
            except Exception as e:
                logger.warning(f"failed to retrieve episodic memories: {e}")

        # Build full prompt with clearly labeled context sections
        prompt_parts = [f"[TODAY]: {date.today().isoformat()}"]

        if thread_context and thread_context != "No previous messages in this thread.":
            prompt_parts.append(f"[CURRENT THREAD - these are the messages in THIS thread]:\n{thread_context}")

        if memory_context:
            prompt_parts.append(f"[PAST CONTEXT WITH @{author_handle}]:\n{memory_context}")

        if episodic_context:
            prompt_parts.append(episodic_context)

        prompt_parts.append(f"\n[NEW MESSAGE]:\n@{author_handle}: {mention_text}")
        prompt = "\n\n".join(prompt_parts)

        # Build multimodal prompt if images are present
        if image_urls:
            user_prompt: str | list = [prompt] + [ImageUrl(url=url) for url in image_urls]
            logger.info(f"including {len(image_urls)} images in prompt")
        else:
            user_prompt = prompt

        # Run agent with MCP tools + search_memory available
        logger.info(f"processing mention from @{author_handle}: {mention_text[:80]}")
        deps = PhiDeps(
            author_handle=author_handle,
            memory=self.memory,
            thread_uri=thread_uri,
        )
        result = await self.agent.run(user_prompt, deps=deps)
        logger.info(f"agent decided: {result.output.action}" + (f" - {result.output.text[:80]}" if result.output.text else "") + (f" ({result.output.reason})" if result.output.reason else ""))

        # Store interaction and extract observations
        if self.memory and result.output.action == "reply" and result.output.text:
            try:
                await self.memory.after_interaction(
                    author_handle, mention_text, result.output.text
                )
            except Exception as e:
                logger.warning(f"failed to store interaction: {e}")

        return result.output
