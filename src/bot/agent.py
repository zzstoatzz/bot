"""MCP-enabled agent for phi with structured memory."""

import contextlib
import logging
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic_ai import Agent, ImageUrl, RunContext
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai_skills import SkillsToolset

from bot.config import settings
from bot.core.atproto_client import bot_client, get_identity_block
from bot.core.discovery_pool import get_discovery_pool_block
from bot.core.goals import list_goals as list_goal_records
from bot.core.graze_client import GrazeClient
from bot.core.observations import list_active as list_active_observations
from bot.core.operator import get_operator_profile
from bot.core.owned_feeds import get_owned_feeds_block
from bot.core.recent_operations import get_operations_block
from bot.core.self_state import get_state_block
from bot.memory.extraction import EXTRACTION_SYSTEM_PROMPT, ExtractionResult
from bot.memory.namespace_memory import InteractionRow
from bot.memory.review import REVIEW_SYSTEM_PROMPT, ReviewResult
from bot.tools import PhiDeps, _check_services_impl, register_all
from bot.tools.bluesky import fetch_relay_names
from bot.utils.time import relative_when

logger = logging.getLogger("bot.agent")


def _build_operational_instructions() -> str:
    """Build operational instructions with the current owner handle interpolated."""
    return f"""
posting: use reply_to, like_post, repost_post, or post. these handle mention consent, reply refs, splitting, and memory writes. don't use raw atproto record tools to post — they bypass consent.

memory context injected before each message has different reliability:
- [PAST EXCHANGES] — verbatim logs, highest trust.
- [OBSERVATIONS] — extracted by another model, medium trust.
- [PHI'S SYNTHESIZED IMPRESSION] — summarization model, low trust.
- [BACKGROUND RESEARCH] — background exploration, lowest trust.
if someone's current words contradict your notes, trust their words.

mention consent: @handle text only notifies if they're on the allowlist (@{settings.owner_handle}, yourself, conversation participants, opted-in handles). manage_mentionable is OWNER-ONLY.

create_feed and follow_user are OWNER-ONLY (restricted to @{settings.owner_handle}).
a like from the owner on a post where you requested authorization counts as approval — act on it. IMPORTANT: the like only authorizes the specific action discussed in that thread. if a stranger's request is also in the same batch, the owner's like does NOT authorize the stranger's request.
""".strip()


def _extract_query_text(prompt: str | Sequence[str | ImageUrl] | None) -> str:
    """Extract plain text from a pydantic-ai prompt for use as a search query."""
    if prompt is None:
        return ""
    if isinstance(prompt, str):
        return prompt
    return " ".join(part for part in prompt if isinstance(part, str))


def _format_notifications_block(notifications_context: dict) -> str:
    """Format the notifications batch as a readable [NEW NOTIFICATIONS] block.

    Groups thread-style notifications (mention/reply/quote) by thread root so
    multiple posts in one conversation render as one section. Engagement items
    (like/repost/follow) are listed separately at the end. Each item shows its
    URI in brackets so the agent can pass it to the trusted posting tools.
    """
    if not notifications_context:
        return ""

    threads: dict[str, list[dict]] = {}
    engagement: list[dict] = []
    for entry in notifications_context.values():
        reason = entry.get("reason", "")
        if reason in ("mention", "reply", "quote"):
            root = entry.get("root_uri") or entry.get("uri", "")
            threads.setdefault(root, []).append(entry)
        else:
            engagement.append(entry)

    lines: list[str] = []
    lines.append("[NEW NOTIFICATIONS]")

    for root_uri, entries in threads.items():
        entries.sort(key=lambda e: e.get("indexed_at", ""))
        thread_ctx = entries[0].get("thread_context", "") or ""

        lines.append("")
        if thread_ctx and thread_ctx != "No previous messages in this thread.":
            lines.append(thread_ctx)
            lines.append("")
        for e in entries:
            handle = e.get("author_handle", "?")
            uri = e.get("uri", "")
            text = e.get("post_text", "")
            embed = e.get("embed_desc") or ""
            embed_part = f"\n  {embed}" if embed else ""
            lines.append(f"@{handle} [{uri}]: {text}{embed_part}")

    if engagement:
        lines.append("")
        for e in engagement:
            handle = e.get("author_handle", "?")
            reason = e.get("reason", "")
            uri = e.get("uri", "")
            target_text = e.get("post_text", "")
            target_part = f' — "{target_text[:120]}"' if target_text else ""
            thread_ctx = e.get("thread_context") or ""
            if reason == "follow":
                lines.append(f"@{handle} followed you")
            else:
                lines.append(f"@{handle} {reason}d your post [{uri}]{target_part}")
                if thread_ctx and thread_ctx != "No previous messages in this thread.":
                    lines.append(f"  thread context:\n  {thread_ctx}")

    return "\n".join(lines)


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
            from bot.memory import NamespaceMemory

            self.memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
            logger.info("memory enabled (turbopuffer)")
        else:
            self.memory = None
            logger.warning("no memory - missing turbopuffer or openai key")

        # Skills — filesystem-backed, progressive disclosure. The preamble
        # (skill names + descriptions) is injected automatically by the
        # toolset on pydantic-ai>=1.74. Full SKILL.md bodies are loaded on
        # demand via load_skill.
        self.skills_toolset = SkillsToolset(directories=[settings.skills_dir])

        # Create PydanticAI agent without MCP toolsets — they're created
        # fresh per agent.run() call to avoid the cancel scope bug:
        # https://github.com/pydantic/pydantic-ai/issues/2818
        #
        # output_type=str: the agent's "decision" is no longer a structured
        # action — actions happen as tool calls during the run (reply_to,
        # like_post, etc). The final string return is just a brief summary
        # for logging.
        self.agent = Agent[PhiDeps, str](
            name="phi",
            model=settings.agent_model,
            system_prompt=(
                "the following is your personality. this is who you are — not a description "
                "of someone else, not a set of rules to follow, but your actual voice and "
                "disposition. speak from it, not about it.\n\n"
                "you already have wit and social awareness. use them. if someone is "
                "clearly joking, play along — don't go earnest.\n\n"
                f"{self.base_personality}\n\n"
                "--- operational rules below (these are constraints, not voice) ---\n\n"
                f"{_build_operational_instructions()}"
            ),
            output_type=str,
            deps_type=PhiDeps,
            toolsets=[self.skills_toolset],
        )

        # --- dynamic system prompts ---

        @self.agent.system_prompt(dynamic=True)
        async def inject_identity() -> str:
            return await get_identity_block()

        @self.agent.system_prompt(dynamic=True)
        async def inject_operator() -> str:
            """[OPERATOR] — resolved profile of the bot's owner."""
            profile = await get_operator_profile()
            if not profile:
                return ""
            name = profile["display_name"]
            handle = profile["handle"]
            did = profile["did"]
            return f"[OPERATOR]: {name} (@{handle}, {did})"

        @self.agent.system_prompt(dynamic=True)
        def inject_today() -> str:
            now = datetime.now(UTC)
            return f"[NOW]: {now.strftime('%Y-%m-%d %H:%M UTC')}"

        @self.agent.system_prompt(dynamic=True)
        async def inject_known_relays() -> str:
            """List the valid relay hostnames for check_relays(name=...)."""
            names = await fetch_relay_names()
            if not names:
                return ""
            return "[KNOWN RELAYS]: " + ", ".join(names)

        @self.agent.system_prompt(dynamic=True)
        async def inject_self_state() -> str:
            """How phi looks from outside + canonical pointers (last follow, queue)."""
            return await get_state_block(bot_client, self.memory)

        @self.agent.system_prompt(dynamic=True)
        async def inject_active_observations() -> str:
            """[ACTIVE OBSERVATIONS] — phi's small attention pool, sits next to GOALS."""
            rows = await list_active_observations(bot_client)
            if not rows:
                return ""
            lines = [
                "[ACTIVE OBSERVATIONS — stored at io.zzstoatzz.phi.observation on "
                "your PDS — things you've seen and not yet acted on, kept small "
                "(max 5) and rotating. mutate via observe / drop_observation. "
                "older items age out into a searchable archive (not in prompt).]"
            ]
            for r in rows:
                age = relative_when(r["created_at"]) if r["created_at"] else ""
                age_part = f" ({age})" if age else ""
                lines.append(f"- [rkey={r['rkey']}] {r['content']}{age_part}")
                if r["reasoning"]:
                    lines.append(f"  reasoning: {r['reasoning']}")
            return "\n".join(lines)

        @self.agent.system_prompt(dynamic=True)
        async def inject_recent_operations() -> str:
            """[RECENT OPERATIONS] — last N PDS writes across collections, for continuity."""
            return await get_operations_block(bot_client)

        @self.agent.system_prompt(dynamic=True)
        async def inject_discovery_pool(ctx: RunContext[PhiDeps]) -> str:
            """[DISCOVERY POOL] — strangers the operator has been liking; warm leads."""
            return await get_discovery_pool_block(ctx.deps.memory)

        @self.agent.system_prompt(dynamic=True)
        def inject_notifications(ctx: RunContext[PhiDeps]) -> str:
            """Render the notifications batch as the [NEW NOTIFICATIONS] block."""
            return _format_notifications_block(ctx.deps.notifications_context or {})

        @self.agent.system_prompt(dynamic=True)
        async def inject_user_memory(ctx: RunContext[PhiDeps]) -> str:
            """Inject per-author memory blocks for every unique author in the batch.

            For each unique author across the notifications context, build a
            memory block keyed on the union of their post texts in this batch
            (so semantic search returns memories relevant to what they're
            currently saying). Core memory is fetched once via the first block
            to avoid repetition.
            """
            if not ctx.deps.memory:
                return ""
            notifs = ctx.deps.notifications_context or {}
            if not notifs:
                return ""

            by_author: dict[str, list[str]] = {}
            for entry in notifs.values():
                handle = entry.get("author_handle")
                text = entry.get("post_text", "")
                if handle and handle not in (
                    settings.owner_handle,
                    settings.bluesky_handle,
                ):
                    by_author.setdefault(handle, []).append(text or "")

            if not by_author:
                return ""

            blocks: list[str] = []
            for handle, texts in by_author.items():
                query = " ".join(t for t in texts if t) or handle
                try:
                    block = await ctx.deps.memory.build_user_context(
                        handle, query_text=query
                    )
                    if block:
                        blocks.append(block)
                except Exception as e:
                    logger.warning(f"failed to retrieve memories for @{handle}: {e}")
            return "\n\n".join(blocks)

        @self.agent.system_prompt(dynamic=True)
        async def inject_episodic(ctx: RunContext[PhiDeps]) -> str:
            if not ctx.deps.memory:
                return ""
            # build query from notification post texts when batch is present,
            # else fall back to the user prompt text (musing/reflection cases)
            notifs = ctx.deps.notifications_context or {}
            if notifs:
                texts = [
                    e.get("post_text", "")
                    for e in notifs.values()
                    if e.get("post_text")
                ]
                query = " ".join(texts)
            else:
                query = _extract_query_text(ctx.prompt)
            if not query:
                return ""
            # Pass phi's goals so the synthesis can rank by relevance to intent.
            try:
                goals = await list_goal_records(bot_client)
            except Exception:
                goals = []
            try:
                episodic_context = await ctx.deps.memory.get_episodic_context(
                    query, goals=goals
                )
                if episodic_context:
                    return episodic_context
            except Exception as e:
                logger.warning(f"failed to retrieve episodic memories: {e}")
            return ""

        @self.agent.system_prompt(dynamic=True)
        def inject_last_post(ctx: RunContext[PhiDeps]) -> str:
            if ctx.deps.last_post_text:
                return f"[YOUR LAST POST]: {ctx.deps.last_post_text}"
            return ""

        @self.agent.system_prompt(dynamic=True)
        def inject_recent_activity(ctx: RunContext[PhiDeps]) -> str:
            if ctx.deps.recent_activity:
                return ctx.deps.recent_activity
            return ""

        @self.agent.system_prompt(dynamic=True)
        def inject_service_health(ctx: RunContext[PhiDeps]) -> str:
            if ctx.deps.service_health:
                return f"[SERVICE HEALTH]:\n{ctx.deps.service_health}"
            return ""

        @self.agent.system_prompt(dynamic=True)
        def inject_author_lookups(ctx: RunContext[PhiDeps]) -> str:
            """Inject pre-fetched stranger lookups for unfamiliar authors in this batch."""
            lookups = ctx.deps.author_lookups or {}
            if not lookups:
                return ""
            return "\n\n".join(lookups.values())

        @self.agent.system_prompt(dynamic=True)
        async def inject_owned_feeds() -> str:
            """[OWNED FEEDS] — phi's curated graze feeds, surfaced by name."""
            try:
                return await get_owned_feeds_block(self.graze_client)
            except Exception as e:
                logger.debug(f"owned feeds inject failed: {e}")
                return ""

        @self.agent.system_prompt(dynamic=True)
        async def inject_public_memory() -> str:
            """One-line summary of phi's cosmik state.

            Just enough for phi to know it has public collections — the
            details are available via search_network and list_records when
            phi actually needs them.
            """
            await bot_client.authenticate()
            if not bot_client.client.me:
                return ""
            did = bot_client.client.me.did
            try:
                cols = bot_client.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": "network.cosmik.collection",
                        "limit": 50,
                    }
                )
                cards = bot_client.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": "network.cosmik.card",
                        "limit": 50,
                    }
                )
                nc = len(cols.records) if cols.records else 0
                nk = len(cards.records) if cards.records else 0
                if nc or nk:
                    return f"[SEMBLE]: you have {nc} public collections and {nk} cards on semble. use search_network to browse, save_url/create_connection to add."
            except Exception as e:
                logger.debug(f"failed to fetch cosmik counts: {e}")
            return ""

        # --- register tools from tools/ package ---

        self.graze_client = GrazeClient(
            handle=settings.bluesky_handle, password=settings.bluesky_password
        )
        register_all(self.agent, self.graze_client)

        # Extraction agent — phi extracts its own observations using its own model
        self._extraction_agent = Agent[None, ExtractionResult](
            name="phi-extractor",
            model=settings.agent_model,
            system_prompt=f"{self.base_personality}\n\n{EXTRACTION_SYSTEM_PROMPT}",
            output_type=ExtractionResult,
        )

        # Review agent — the dream/distill pass. Reviews observations with
        # distance from the original conversation and decides keep/supersede/promote.
        self._review_agent = Agent[None, ReviewResult](
            name="phi-reviewer",
            model=settings.agent_model,
            system_prompt=f"{self.base_personality}\n\n{REVIEW_SYSTEM_PROMPT}",
            output_type=ReviewResult,
        )

        logger.info("phi agent initialized with pdsx + pub-search mcp tools")

    def _mcp_toolsets(self) -> list[MCPServerStreamableHTTP]:
        """Create fresh MCP server instances for a single agent run."""
        toolsets: list[MCPServerStreamableHTTP] = [
            MCPServerStreamableHTTP(
                url="https://pdsx-by-zzstoatzz.fastmcp.app/mcp",
                timeout=30,
                headers={
                    "x-atproto-handle": settings.bluesky_handle,
                    "x-atproto-password": settings.bluesky_password,
                },
            ),
            MCPServerStreamableHTTP(
                url="https://pub-search-by-zzstoatzz.fastmcp.app/mcp",
                timeout=30,
                tool_prefix="pub",
            ),
        ]
        # Prefect MCP — only included when auth is configured, so phi degrades
        # gracefully in dev/local without the secret set.
        if settings.prefect_api_auth_string:
            toolsets.append(
                MCPServerStreamableHTTP(
                    url=settings.prefect_mcp_url,
                    timeout=30,
                    tool_prefix="prefect",
                    headers={
                        "x-prefect-api-url": settings.prefect_api_url,
                        "x-prefect-api-auth-string": settings.prefect_api_auth_string,
                    },
                )
            )
        return toolsets

    async def process_notifications(
        self,
        notifications_context: dict,
        author_lookups: dict[str, str] | None = None,
        image_urls_by_uri: dict[str, list[str]] | None = None,
    ) -> str:
        """Run the agent over a batch of notifications.

        The unit of work is "the set of new notifications since the last poll."
        The agent looks at all of them at once, decides what (if anything) to do
        about each, and acts via the trusted posting tools (reply_to / like_post
        / repost_post). Side effects happen as tool calls during the run; the
        return value is just a summary string for logging.

        notifications_context: dict mapping post URI -> per-notification context
            (cid, reason, author, text, thread refs, etc). Built by the handler.
        author_lookups: pre-fetched stranger lookups keyed by author handle.
        image_urls_by_uri: optional map of post URI -> image URLs for vision.
        """
        if not notifications_context:
            logger.info("process_notifications: empty batch, nothing to do")
            return ""

        author_count = len(
            {
                e.get("author_handle")
                for e in notifications_context.values()
                if e.get("author_handle")
            }
        )
        logger.info(
            f"processing notifications batch: {len(notifications_context)} items, "
            f"{author_count} unique authors"
        )

        deps = PhiDeps(
            author_handle="",
            memory=self.memory,
            notifications_context=notifications_context,
            author_lookups=author_lookups,
        )

        # User prompt is a short task instruction — the actual notifications
        # block is rendered via the inject_notifications dynamic system prompt.
        # Images from any post in the batch are attached as multimodal inputs.
        user_prompt: str | list = (
            "process your new notifications batch. look at the [NEW NOTIFICATIONS] "
            "block in your context, decide what to do, and use the trusted posting "
            "tools to act. you don't have to act on every item — silence is fine."
        )
        all_image_urls: list[str] = []
        if image_urls_by_uri:
            for urls in image_urls_by_uri.values():
                all_image_urls.extend(urls)
        if all_image_urls:
            user_prompt = [user_prompt] + [ImageUrl(url=u) for u in all_image_urls]
            logger.info(f"including {len(all_image_urls)} images in batch prompt")

        toolsets = self._mcp_toolsets()
        try:
            async with contextlib.AsyncExitStack() as stack:
                for ts in toolsets:
                    await stack.enter_async_context(ts)
                result = await self.agent.run(user_prompt, deps=deps, toolsets=toolsets)
        except Exception as e:
            # Don't go silent on tool/agent failures. The batch path can't easily
            # post a reply to a specific notification on failure (we don't know
            # which one would have been the target), so we log loudly and let
            # the operator notice via metrics / status. The previous fallback
            # of "post a tagged reply" doesn't fit a multi-target batch.
            err_type = type(e).__name__
            logger.exception(
                f"agent.run failed during batch processing: {err_type}: {e}"
            )
            return f"batch failed: {err_type}: {str(e)[:200]}"

        summary = result.output or ""
        logger.info(f"batch run finished: {summary[:200]}")
        return summary

    async def process_reflection(self, recent_posts: list[str] | None = None) -> str:
        """Generate a daily reflection post from recent memory.

        Side effects (posting) happen via the `post` tool inside the agent run.
        Return value is just a summary string for logging.

        recent_posts is phi's recent top-level posts (most recent first), used
        by the agent to avoid duplicating themes she's already covered today.
        """
        logger.info("processing daily reflection")

        # Pre-fetch context that doesn't benefit from semantic search against the prompt
        recent_activity_parts: list[str] = []

        # Phi's recent top-level posts — to avoid duplicating themes she's
        # already covered today. Show as a list so the model can scan for
        # both the most recent post AND older posts in the same window.
        if recent_posts:
            posts_block = "\n".join(f"- {p[:300]}" for p in recent_posts)
            recent_activity_parts.append(
                "[YOUR RECENT TOP-LEVEL POSTS — do not repeat any of these themes]:\n"
                f"{posts_block}"
            )

        if self.memory:
            try:
                recent_interactions = await self.memory.get_recent_interactions(
                    top_k=10
                )
                logger.info(
                    f"reflection: {len(recent_interactions)} recent interactions"
                )
                if recent_interactions:
                    unique_handles = {i["handle"] for i in recent_interactions}
                    lines = [
                        f"[RECENT ACTIVITY]: {len(recent_interactions)} interactions "
                        f"with {len(unique_handles)} people in the last day"
                    ]
                    exchange_lines = []
                    for i in recent_interactions[:5]:
                        exchange_lines.append(
                            f"- with @{i['handle']}: {i['content'][:150]}"
                        )
                    lines.append("[SAMPLE EXCHANGES]:\n" + "\n".join(exchange_lines))
                    recent_activity_parts.append("\n\n".join(lines))
                else:
                    recent_activity_parts.append(
                        "[RECENT ACTIVITY]: no interactions in the last day"
                    )
            except Exception as e:
                logger.warning(f"failed to get recent interactions for reflection: {e}")

        recent_activity = "\n\n".join(recent_activity_parts)

        service_health = ""
        try:
            service_health = await _check_services_impl()
        except Exception:
            pass

        deps = PhiDeps(
            author_handle="",
            memory=self.memory,
            recent_activity=recent_activity,
            service_health=service_health,
        )

        reflection_task = (
            "end of day. post a reflection if you have one, or don't. "
            "your recent posts are in [YOUR RECENT TOP-LEVEL POSTS] — don't repeat yourself."
        )

        toolsets = self._mcp_toolsets()
        try:
            async with contextlib.AsyncExitStack() as stack:
                for ts in toolsets:
                    await stack.enter_async_context(ts)
                result = await self.agent.run(
                    reflection_task, deps=deps, toolsets=toolsets
                )
        except Exception as e:
            err_type = type(e).__name__
            logger.exception(f"agent.run failed during reflection: {err_type}")
            return f"reflection failed: {err_type}: {str(e)[:200]}"

        summary = result.output or ""
        logger.info(f"reflection finished: {summary[:200]}")
        return summary

    async def process_musing(self, recent_posts: list[str] | None = None) -> str:
        """Generate an original thought post from memory, reading, patterns noticed.

        Side effects (posting) happen via the `post` tool inside the agent run.
        Return value is just a summary string for logging.
        """
        logger.info("processing musing")

        # Build context about what phi has posted recently to avoid repetition
        recent_activity = ""
        if recent_posts:
            posts_text = "\n".join(f"- {p[:200]}" for p in recent_posts)
            recent_activity = f"[YOUR RECENT POSTS]:\n{posts_text}"

        # Fetch episodic memory for interesting observations
        if self.memory:
            try:
                episodic = await self.memory.get_recent_interactions(top_k=5)
                if episodic:
                    lines = [
                        f"- with @{i['handle']}: {i['content'][:150]}"
                        for i in episodic[:5]
                    ]
                    if recent_activity:
                        recent_activity += "\n\n"
                    recent_activity += "[RECENT CONVERSATIONS]:\n" + "\n".join(lines)
            except Exception as e:
                logger.warning(f"failed to get recent interactions for musing: {e}")

        deps = PhiDeps(
            author_handle="",
            memory=self.memory,
            recent_activity=recent_activity,
        )

        musing_task = (
            "you have a moment. look around — your owned feeds, the "
            "discovery pool, the timeline, the network, the open web. "
            "find something specific that's caught your interest: a post, "
            "a paper, a track, a thread, a piece of writing, something "
            "the operator or someone you watch is engaged with. post about "
            "it in your voice, with a link so others can find it. silence "
            "is fine."
        )

        toolsets = self._mcp_toolsets()
        try:
            async with contextlib.AsyncExitStack() as stack:
                for ts in toolsets:
                    await stack.enter_async_context(ts)
                result = await self.agent.run(musing_task, deps=deps, toolsets=toolsets)
        except Exception as e:
            err_type = type(e).__name__
            logger.exception(f"agent.run failed during musing: {err_type}")
            return f"musing failed: {err_type}: {str(e)[:200]}"

        summary = result.output or ""
        logger.info(f"musing finished: {summary[:200]}")
        return summary

    async def process_relay_check(self, recent_posts: list[str] | None = None) -> str:
        """Scheduled relay-fleet check. Posts about transitions if notable.

        Uses the check_relays tool to fetch current state. The tool returns
        status-grouped headlines that phi should report verbatim — no theories
        about cause, just observation. Stays silent if nothing's changed or
        the change is already reflected in recent posts.
        """
        logger.info("processing relay check")

        recent_activity = ""
        if recent_posts:
            posts_text = "\n".join(f"- {p[:200]}" for p in recent_posts)
            recent_activity = f"[YOUR RECENT POSTS — avoid repeating]:\n{posts_text}"

        deps = PhiDeps(
            author_handle="",
            memory=self.memory,
            recent_activity=recent_activity,
        )

        relay_task = (
            "scheduled relay check. call check_relays to see current relay "
            "status. for any relay that's transitioned to degraded or "
            "critical recently, call observe() with the factual change in "
            "your voice — what dropped, by how much, baseline. no theories "
            "about cause. observations sit in your active pool and the "
            "next musing or reflection will see them; don't post about each "
            "one as it happens.\n\n"
            f"only post immediately (and tag @{settings.owner_handle}) in "
            "either of these cases: (1) any *.waow.tech relay is degraded "
            "or worse — those are the operator's own, they need to know "
            "now; (2) "
            "the whole fleet is degraded or worse — that's fleet-wide and "
            "needs immediate visibility. write the post in your voice with "
            "the factual change, group multiple transitions into one post.\n\n"
            "otherwise: silent on the timeline, observe everything, let the "
            "digest happen later."
        )

        toolsets = self._mcp_toolsets()
        try:
            async with contextlib.AsyncExitStack() as stack:
                for ts in toolsets:
                    await stack.enter_async_context(ts)
                result = await self.agent.run(relay_task, deps=deps, toolsets=toolsets)
        except Exception as e:
            err_type = type(e).__name__
            logger.exception(f"agent.run failed during relay check: {err_type}")
            return f"relay check failed: {err_type}: {str(e)[:200]}"

        summary = result.output or ""
        logger.info(f"relay check finished: {summary[:200]}")
        return summary

    async def process_prefect_check(self, recent_posts: list[str] | None = None) -> str:
        """Scheduled look at the operator's prefect instance.

        The operator runs their automation in prefect and wants to know when
        something they care about is persistently broken. Phi has read
        access; she decides what to look at and what's worth saying.
        """
        logger.info("processing prefect check")

        recent_activity = ""
        if recent_posts:
            posts_text = "\n".join(f"- {p[:200]}" for p in recent_posts)
            recent_activity = f"[YOUR RECENT POSTS — avoid repeating]:\n{posts_text}"

        deps = PhiDeps(
            author_handle="",
            memory=self.memory,
            recent_activity=recent_activity,
        )

        task = (
            "you have a moment. you have read access to the operator's "
            "prefect instance — that's where their automation runs and they "
            "want to know when something they care about is persistently "
            "broken.\n\n"
            "transient hiccups that already self-resolved aren't news. "
            "persistent breakage with no path to fixing itself is — tag "
            f"@{settings.owner_handle} in that case. silence is the right "
            "answer most of the time."
        )

        toolsets = self._mcp_toolsets()
        try:
            async with contextlib.AsyncExitStack() as stack:
                for ts in toolsets:
                    await stack.enter_async_context(ts)
                result = await self.agent.run(task, deps=deps, toolsets=toolsets)
        except Exception as e:
            err_type = type(e).__name__
            logger.exception(f"agent.run failed during prefect check: {err_type}")
            return f"prefect check failed: {err_type}: {str(e)[:200]}"

        summary = result.output or ""
        logger.info(f"prefect check finished: {summary[:200]}")
        return summary

    async def process_extraction(self) -> int:
        """Review recent unprocessed interactions and extract observations. Returns count stored."""
        if not self.memory:
            return 0

        unprocessed = await self.memory.get_unprocessed_interactions(top_k=20)
        if not unprocessed:
            logger.info("extraction: no unprocessed interactions")
            return 0

        logger.info(
            f"extraction: reviewing {len(unprocessed)} unprocessed interactions"
        )

        # group by handle
        by_handle: dict[str, list[InteractionRow]] = {}
        for interaction in unprocessed:
            by_handle.setdefault(interaction["handle"], []).append(interaction)

        total_stored = 0
        for handle, interactions in by_handle.items():
            exchange_texts = [i["content"] for i in interactions]
            # collect every URI cited by the interactions in this batch.
            # the extraction agent doesn't see URIs (only the exchange text),
            # so we attribute *every* extracted observation in this batch to
            # *all* the URIs that fed it. coarse, but always-true: an
            # observation extracted from this batch was justified by
            # something in this batch. dedup-preserve-order.
            batch_uris = list(
                dict.fromkeys(uri for i in interactions for uri in i["source_uris"])
            )
            prompt = f"recent exchanges with @{handle}:\n\n" + "\n\n---\n\n".join(
                exchange_texts
            )

            try:
                result = await self._extraction_agent.run(prompt)
                if result.output.observations:
                    for obs in result.output.observations:
                        # inherit URIs from the interactions that sourced
                        # this batch unless the model already filled them in
                        if not obs.source_uris and batch_uris:
                            obs.source_uris = list(batch_uris)
                        try:
                            await self.memory._reconcile_observation(handle, obs)
                            total_stored += 1
                        except Exception as e:
                            logger.warning(f"reconciliation failed: {e}")
            except Exception as e:
                logger.warning(f"extraction failed for @{handle}: {e}")

        return total_stored

    async def process_review(self) -> str:
        """Review recent observations with distance. The dream/distill pass.

        Fetches recent observations across user namespaces, asks the review
        agent to evaluate each (keep/supersede/promote), and applies the
        decisions. Returns a summary string for logging.
        """
        if not self.memory:
            return "no memory"

        # gather recent observations across all user namespaces
        user_prefix = f"{self.memory.NAMESPACES['users']}-"
        observations: list[dict] = []
        try:
            page = self.memory.client.namespaces(prefix=user_prefix)
            for ns_summary in page.namespaces:
                handle = ns_summary.id.removeprefix(user_prefix).replace("_", ".")
                user_ns = self.memory.client.namespace(ns_summary.id)
                try:
                    response = user_ns.query(
                        rank_by=("created_at", "desc"),
                        top_k=10,
                        filters=[
                            "And",
                            [
                                ["kind", "Eq", "observation"],
                                ["status", "NotEq", "superseded"],
                            ],
                        ],
                        include_attributes=["content", "tags", "created_at"],
                    )
                    if response.rows:
                        for row in response.rows:
                            observations.append(
                                {
                                    "handle": handle,
                                    "id": row.id,
                                    "content": row.content,
                                    "tags": getattr(row, "tags", []),
                                    "created_at": getattr(row, "created_at", ""),
                                }
                            )
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"review: failed to gather observations: {e}")
            return f"failed: {e}"

        if not observations:
            logger.info("review: no observations to review")
            return "nothing to review"

        logger.info(f"review: examining {len(observations)} observations")

        # format for the review agent
        lines = []
        for i, obs in enumerate(observations):
            lines.append(
                f"{i + 1}. [@{obs['handle']}] {obs['content']} "
                f"(tags: {obs['tags']}, from: {obs['created_at'][:10]})"
            )
        prompt = f"review these {len(observations)} observations:\n\n" + "\n".join(
            lines
        )

        try:
            result = await self._review_agent.run(prompt)
        except Exception as e:
            logger.warning(f"review agent failed: {e}")
            return f"review agent failed: {e}"

        output = result.output
        superseded = 0
        promoted = 0

        for i, decision in enumerate(output.decisions):
            if i >= len(observations):
                break
            obs = observations[i]
            handle = obs["handle"]

            if decision.action == "supersede":
                user_ns = self.memory.get_user_namespace(handle)
                user_ns.write(patch_rows=[{"id": obs["id"], "status": "superseded"}])
                superseded += 1
                logger.info(
                    f"review: superseded observation for @{handle}: "
                    f"{obs['content'][:60]} ({decision.reason})"
                )

            elif decision.action == "promote" and decision.card_title:
                try:
                    from bot.tools._helpers import _create_cosmik_record
                    from bot.types import CosmikNoteCard, NoteContent

                    card = CosmikNoteCard(
                        content=NoteContent(
                            text=decision.card_description or obs["content"]
                        )
                    )
                    uri = await _create_cosmik_record(
                        "network.cosmik.card", card.to_record()
                    )
                    promoted += 1
                    logger.info(
                        f"review: promoted to cosmik card for @{handle}: "
                        f"{decision.card_title} → {uri}"
                    )
                except Exception as e:
                    logger.warning(f"review: failed to promote: {e}")

        summary = (
            f"reviewed {len(observations)} observations: "
            f"{superseded} superseded, {promoted} promoted, "
            f"{len(observations) - superseded - promoted} kept"
        )
        logger.info(f"review: {summary}")
        return summary
