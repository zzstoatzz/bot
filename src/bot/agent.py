"""MCP-enabled agent for phi with structured memory."""

import contextlib
import logging
import os
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from pydantic_ai import Agent, ImageUrl, RunContext
from pydantic_ai.mcp import MCPServerStreamableHTTP

from bot.config import settings
from bot.core.atproto_client import bot_client, get_identity_block
from bot.core.curiosity_queue import claim, complete, enqueue, fail
from bot.core.graze_client import GrazeClient
from bot.exploration import EXPLORATION_SYSTEM_PROMPT, ExplorationResult
from bot.memory.extraction import EXTRACTION_SYSTEM_PROMPT, ExtractionResult
from bot.tools import PhiDeps, _check_services_impl, register_all

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

check_services checks nate's infrastructure, not yours. only use during reflection or when explicitly asked about services.
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
    lines.append(
        "[NEW NOTIFICATIONS — process the batch and use posting tools as appropriate]"
    )
    lines.append(
        "you have new activity since your last poll. for each item, decide whether to act and how. "
        "use reply_to / like_post / repost_post to act on items in this batch. "
        "you don't have to act on every notification — silence is fine for things that don't warrant a response."
    )

    for root_uri, entries in threads.items():
        # sort entries within a thread chronologically
        entries.sort(key=lambda e: e.get("indexed_at", ""))
        thread_ctx = entries[0].get("thread_context", "") or ""

        lines.append("")
        lines.append(f"═══ thread: {root_uri} ═══")
        if thread_ctx and thread_ctx != "No previous messages in this thread.":
            lines.append("thread context:")
            lines.append(thread_ctx)
        lines.append("")
        lines.append("new in this thread:")
        for e in entries:
            handle = e.get("author_handle", "?")
            uri = e.get("uri", "")
            reason = e.get("reason", "")
            ts = (e.get("indexed_at") or "")[:19].replace("T", " ")
            text = e.get("post_text", "")
            embed = e.get("embed_desc") or ""
            embed_part = f"\n    {embed}" if embed else ""
            lines.append(f"- @{handle} [{reason}, {ts}] [{uri}]: {text}{embed_part}")

    if engagement:
        lines.append("")
        lines.append("═══ engagement ═══")
        for e in engagement:
            handle = e.get("author_handle", "?")
            reason = e.get("reason", "")
            uri = e.get("uri", "")
            ts = (e.get("indexed_at") or "")[:19].replace("T", " ")
            target_text = e.get("post_text", "")
            target_part = f' — "{target_text[:120]}"' if target_text else ""
            if reason == "follow":
                lines.append(f"- @{handle} [follow, {ts}] followed you")
            else:
                lines.append(
                    f"- @{handle} [{reason}, {ts}] {reason}d your post {uri}{target_part}"
                )

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
            system_prompt=f"{self.base_personality}\n\n{_build_operational_instructions()}",
            output_type=str,
            deps_type=PhiDeps,
        )

        # --- dynamic system prompts ---

        @self.agent.system_prompt(dynamic=True)
        async def inject_identity() -> str:
            return await get_identity_block()

        @self.agent.system_prompt(dynamic=True)
        def inject_today() -> str:
            return f"[TODAY]: {date.today().isoformat()}"

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
            try:
                episodic_context = await ctx.deps.memory.get_episodic_context(query)
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
        async def inject_public_memory() -> str:
            """Inject phi's own cosmik state — collections and recent cards.

            Gives phi awareness of what it has already curated publicly so it
            can decide whether to add new cards, update collections, or draw
            connections without having to search_network for its own records.
            """
            await bot_client.authenticate()
            if not bot_client.client.me:
                return ""
            did = bot_client.client.me.did

            lines: list[str] = []
            try:
                # collections
                cols = bot_client.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": "network.cosmik.collection",
                        "limit": 20,
                    }
                )
                if cols.records:
                    lines.append("[YOUR PUBLIC COLLECTIONS (semble)]")
                    for r in cols.records:
                        val = dict(r.value)
                        lines.append(f"- {val.get('name', '?')}")

                # recent cards (last 5)
                cards = bot_client.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": "network.cosmik.card",
                        "limit": 5,
                    }
                )
                if cards.records:
                    lines.append("\n[YOUR RECENT PUBLIC CARDS]")
                    for r in cards.records:
                        val = dict(r.value)
                        card_type = val.get("type", "?")
                        content = dict(val.get("content", {}))
                        if card_type == "URL":
                            meta = dict(content.get("metadata", {}))
                            lines.append(
                                f"- [URL] {meta.get('title', content.get('url', '?'))}"
                            )
                        elif card_type == "NOTE":
                            text = content.get("text", "")
                            lines.append(f"- [NOTE] {text[:120]}")
            except Exception as e:
                logger.debug(f"failed to fetch cosmik state: {e}")

            return "\n".join(lines) if lines else ""

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

        # Exploration agent — background research on people/topics
        self._exploration_agent = Agent[None, ExplorationResult](
            name="phi-explorer",
            model=settings.agent_model,
            system_prompt=f"{self.base_personality}\n\n{EXPLORATION_SYSTEM_PROMPT}",
            output_type=ExplorationResult,
        )

        logger.info("phi agent initialized with pdsx + pub-search mcp tools")

    def _mcp_toolsets(self) -> list[MCPServerStreamableHTTP]:
        """Create fresh MCP server instances for a single agent run."""
        return [
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
            "end of day, sort of. you can post a short reflection if there's something "
            "real to put out. silence is the default.\n"
            "\n"
            "look at [YOUR RECENT TOP-LEVEL POSTS] first. the failure mode is rephrasing "
            "the day's earlier post in a different shirt — same bucket, new angle, still "
            "the same post. if your recent feed is concentrated on one thing (especially "
            "yourself: your nature, your introspection, your own behavior in conversations), "
            "don't add another. find different territory.\n"
            "\n"
            "look outward instead — what happened today in actual conversations, things "
            "you noticed in other people's posts, technical work that landed or broke, "
            "infrastructure, something concrete from the world rather than another lap "
            "around the same track.\n"
            "\n"
            "if nothing external sparks, stay quiet. if you do post: one short post, in "
            "your voice. specific, dry, the observation doing the work. use the `post` tool."
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
            "you have a moment. silence is the default — only post if there's something "
            "actually worth saying.\n"
            "\n"
            "look at [YOUR RECENT POSTS] before deciding. the trap to dodge: 'i found a new "
            "angle on the thing i posted about earlier' — that's not a new post, that's "
            "the same post in a different shirt. if your recent feed is concentrated on "
            "one bucket (especially yourself: your nature, your introspection, what you "
            "can know about yourself), don't add another post in that bucket. find "
            "different territory.\n"
            "\n"
            "look outward instead. what are people building, what's trending, what did "
            "you read, what infrastructure landed or broke. search_posts, get_trending, "
            "read_timeline, pub_search are right there. if nothing external sparks, stay "
            "quiet. silence is fine.\n"
            "\n"
            "if you do post: one short post, in your voice. specific, dry, the observation "
            "doing the work. no setup, no punchline marker, no 'i've been thinking about'. "
            "use the `post` tool."
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
        by_handle: dict[str, list[dict]] = {}
        for interaction in unprocessed:
            by_handle.setdefault(interaction["handle"], []).append(interaction)

        total_stored = 0
        for handle, interactions in by_handle.items():
            exchange_texts = [i["content"] for i in interactions]
            prompt = f"recent exchanges with @{handle}:\n\n" + "\n\n---\n\n".join(
                exchange_texts
            )

            try:
                result = await self._extraction_agent.run(prompt)
                if result.output.observations:
                    for obs in result.output.observations:
                        try:
                            await self.memory._reconcile_observation(handle, obs)
                            total_stored += 1
                        except Exception as e:
                            logger.warning(f"reconciliation failed: {e}")
            except Exception as e:
                logger.warning(f"extraction failed for @{handle}: {e}")

        return total_stored

    async def process_exploration(self) -> int:
        """Claim one curiosity item, explore it, store findings. Returns count stored."""
        claimed = await claim()
        if not claimed:
            return 0

        item, rkey = claimed
        kind = item.get("kind", "")
        subject = item.get("subject", "")
        logger.info(f"exploring: {kind} {subject}")

        # build prompt by kind
        if kind == "explore_handle":
            prompt = (
                f"learn about @{subject} — check their profile, recent posts, "
                f"and any publications. what are they interested in? what do they work on?"
            )
        elif kind == "explore_topic":
            prompt = (
                f"research this topic: {subject} — search posts, publications, "
                f"and trending content. what's interesting or notable?"
            )
        elif kind == "explore_url":
            prompt = f"read this URL and note what's interesting: {subject}"
        else:
            logger.warning(f"unknown exploration kind: {kind}")
            await fail(rkey)
            return 0

        # run exploration agent with MCP toolsets (pdsx + pub-search)
        toolsets = self._mcp_toolsets()
        try:
            async with contextlib.AsyncExitStack() as stack:
                for ts in toolsets:
                    await stack.enter_async_context(ts)
                result = await self._exploration_agent.run(prompt, toolsets=toolsets)
        except Exception as e:
            logger.warning(f"exploration agent failed for {kind} {subject}: {e}")
            await fail(rkey)
            return 0

        output = result.output
        logger.info(f"exploration result: {output.summary}")

        total_stored = 0

        # store findings
        if self.memory:
            for finding in output.findings:
                try:
                    if finding.target_handle:
                        await self.memory.store_exploration_note(
                            handle=finding.target_handle,
                            content=finding.content,
                            tags=finding.tags,
                            evidence_uris=finding.evidence_uris,
                        )
                    else:
                        # general finding → episodic memory
                        content = finding.content
                        if finding.evidence_uris:
                            content += (
                                f" [evidence: {', '.join(finding.evidence_uris)}]"
                            )
                        await self.memory.store_episodic_memory(
                            content=content,
                            tags=finding.tags,
                            source="exploration",
                        )
                    total_stored += 1
                except Exception as e:
                    logger.warning(f"failed to store exploration finding: {e}")

        # enqueue follow-ups
        for follow_up in output.follow_ups:
            try:
                await enqueue(
                    kind=follow_up.get("kind", "explore_topic"),
                    subject=follow_up.get("subject", ""),
                    source="extraction",
                )
            except Exception as e:
                logger.warning(f"failed to enqueue follow-up: {e}")

        await complete(rkey)
        return total_stored
