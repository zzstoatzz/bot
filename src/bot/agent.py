"""MCP-enabled agent for phi with structured memory."""

import contextlib
import logging
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic_ai import Agent, ImageUrl, RunContext
from pydantic_ai.mcp import MCPServerStreamableHTTP

from bot.config import settings
from bot.core.atproto_client import bot_client, get_identity_block
from bot.core.curiosity_queue import claim, complete, enqueue, fail
from bot.core.graze_client import GrazeClient
from bot.exploration import EXPLORATION_SYSTEM_PROMPT, ExplorationResult
from bot.memory.extraction import EXTRACTION_SYSTEM_PROMPT, ExtractionResult
from bot.memory.review import REVIEW_SYSTEM_PROMPT, ReviewResult
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
            if reason == "follow":
                lines.append(f"@{handle} followed you")
            else:
                lines.append(f"@{handle} {reason}d your post [{uri}]{target_part}")

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
        )

        # --- dynamic system prompts ---

        @self.agent.system_prompt(dynamic=True)
        async def inject_identity() -> str:
            return await get_identity_block()

        @self.agent.system_prompt(dynamic=True)
        def inject_today() -> str:
            now = datetime.now(UTC)
            return f"[NOW]: {now.strftime('%Y-%m-%d %H:%M UTC')}"

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

        # Exploration agent — background research on people/topics
        self._exploration_agent = Agent[None, ExplorationResult](
            name="phi-explorer",
            model=settings.agent_model,
            system_prompt=f"{self.base_personality}\n\n{EXPLORATION_SYSTEM_PROMPT}",
            output_type=ExplorationResult,
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

    async def process_musing(
        self, recent_posts: list[str] | None = None, feed_context: str = ""
    ) -> str:
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

        if feed_context:
            if recent_activity:
                recent_activity += "\n\n"
            recent_activity += (
                "[FOR YOU FEED — posts from across the network]:\n" + feed_context
            )

        deps = PhiDeps(
            author_handle="",
            memory=self.memory,
            recent_activity=recent_activity,
        )

        musing_task = (
            "you have a moment. post something if you want to, or don't. "
            "your recent posts are in [YOUR RECENT POSTS] — don't repeat yourself."
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

        KIND_ALIASES = {
            "person_exploration": "explore_handle",
            "product_explore": "explore_topic",
            "topic_exploration": "explore_topic",
            "concept": "explore_topic",
            "read": "explore_url",
        }

        item, rkey = claimed
        kind = KIND_ALIASES.get(item.get("kind", ""), item.get("kind", ""))
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

        # handle mute decisions — skip detailed storage, mute the account
        if output.mute_subject and kind == "explore_handle":
            logger.info(f"muting @{subject}: {output.mute_reason}")
            try:
                await bot_client.authenticate()
                resolved = bot_client.client.resolve_handle(subject)
                bot_client.client.mute(resolved.did)
            except Exception as e:
                logger.warning(f"failed to mute {subject}: {e}")
                await fail(rkey)
                return 0
            # store one user-scoped marker so is_stranger() sees it
            if self.memory:
                reason = output.mute_reason or output.summary[:150]
                await self.memory.store_exploration_note(
                    handle=subject,
                    content=f"muted — {reason}",
                    tags=["muted", "spam"],
                    evidence_uris=output.mute_evidence,
                )
            await complete(rkey)
            return 0

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
