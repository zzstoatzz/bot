"""Message handler — batch-based notification processing.

The unit of work is a *poll cycle*: each poll dispatches one batch task that
covers every unread notification at once. The handler fetches the necessary
context (post bodies, thread state, stranger lookups), builds the structured
notifications_context dict, and runs the agent once. Side effects (replies,
likes, reposts) happen as tool calls inside the agent run, not as Response
interpretation in the handler.

This means: when an author posts a chain of replies in one thread, phi sees
them as one logical conversation and responds at most once. When a busy hour
brings activity in three different threads, phi makes one decision covering
all of them.
"""

import logging

import logfire
from limits import parse as parse_limit
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from bot.agent import PhiAgent
from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.status import bot_status
from bot.utils.lookup import fetch_author_lookup
from bot.utils.thread import (
    build_thread_context,
    describe_embed,
    extract_image_urls,
    resolve_facet_links,
)

logger = logging.getLogger("bot.handler")

_storage = MemoryStorage()
_limiter = MovingWindowRateLimiter(_storage)
_user_limit = parse_limit("30/hour")


class MessageHandler:
    """Handles incoming notifications using phi agent."""

    def __init__(self, client: BotClient):
        self.client = client
        self.agent = PhiAgent()

    async def _maybe_lookup_stranger(self, author_handle: str) -> str | None:
        """If author is unfamiliar to phi, fetch their profile + recent posts."""
        if not self.agent.memory:
            return None
        if author_handle in (settings.owner_handle, settings.bluesky_handle):
            return None
        try:
            if not await self.agent.memory.is_stranger(author_handle):
                return None
        except Exception as e:
            logger.debug(f"is_stranger check failed for @{author_handle}: {e}")
            return None
        try:
            return await fetch_author_lookup(self.client, author_handle)
        except Exception as e:
            logger.debug(f"author lookup failed for @{author_handle}: {e}")
            return None

    async def _build_post_entry(self, notification) -> dict | None:
        """Build the notifications_context entry for a mention/reply/quote.

        Fetches the post body, thread context, embed description, and reply refs
        so the trusted posting tools can act on the URI without needing to
        re-fetch anything.
        """
        post_uri = notification.uri
        try:
            posts_resp = await self.client.get_posts([post_uri])
        except Exception as e:
            logger.warning(f"failed to fetch post {post_uri}: {e}")
            return None
        if not posts_resp.posts:
            logger.warning(f"could not find post {post_uri}")
            return None
        post = posts_resp.posts[0]

        text = resolve_facet_links(post.record)
        author_handle = post.author.handle

        embed = post.embed if hasattr(post, "embed") and post.embed else None
        if not embed and hasattr(post.record, "embed") and post.record.embed:
            embed = post.record.embed
        embed_desc = describe_embed(embed) if embed else None
        image_urls = extract_image_urls(embed) if embed else []

        # Determine thread root + parent ref
        if hasattr(post.record, "reply") and post.record.reply:
            root_uri = post.record.reply.root.uri
            root_cid = post.record.reply.root.cid
            thread_uri = root_uri
        else:
            root_uri = post_uri
            root_cid = post.cid
            thread_uri = post_uri

        # Fetch thread context for the conversation
        thread_context = "No previous messages in this thread."
        try:
            thread_data = await self.client.get_thread(thread_uri, depth=100)
            thread_context = build_thread_context(thread_data.thread)
        except Exception as e:
            logger.warning(f"failed to fetch thread context for {thread_uri}: {e}")

        return {
            "uri": post_uri,
            "cid": post.cid,
            "reason": notification.reason,
            "author_handle": author_handle,
            "author_did": getattr(post.author, "did", ""),
            "post_text": text,
            "embed_desc": embed_desc or "",
            "image_urls": image_urls,
            "root_uri": root_uri,
            "root_cid": root_cid,
            "thread_uri": thread_uri,
            "thread_context": thread_context,
            "indexed_at": getattr(post, "indexed_at", "") or "",
        }

    async def _build_engagement_entry(self, notification) -> dict | None:
        """Build the notifications_context entry for a like/repost.

        notification.uri is the engagement record (like/repost), NOT the post.
        notification.reason_subject is the URI of phi's post that was engaged
        with. We fetch that post for context + thread history.
        """
        # reason_subject is the actual post that was liked/reposted
        post_uri = getattr(notification, "reason_subject", None) or notification.uri
        post_text = ""
        cid = ""
        root_uri = post_uri
        root_cid = ""
        thread_uri = post_uri
        thread_context = ""
        with logfire.span(
            "build engagement entry",
            post_uri=post_uri,
            engagement_uri=notification.uri,
            author=notification.author.handle,
            reason=notification.reason,
        ):
            try:
                posts_resp = await self.client.get_posts([post_uri])
                if posts_resp.posts:
                    p = posts_resp.posts[0]
                    post_text = p.record.text if hasattr(p.record, "text") else ""
                    cid = p.cid
                    root_cid = cid

                    has_reply = hasattr(p.record, "reply") and p.record.reply
                    logger.info(
                        f"engagement on {post_uri}: has_reply={has_reply}, "
                        f"text={post_text[:80]}"
                    )

                    # resolve thread refs so phi sees the full conversation
                    if has_reply:
                        root_uri = p.record.reply.root.uri
                        root_cid = p.record.reply.root.cid
                        thread_uri = root_uri
                        logger.info(f"fetching thread context from {thread_uri}")

                    try:
                        thread_data = await self.client.get_thread(
                            thread_uri, depth=100
                        )
                        thread_context = build_thread_context(thread_data.thread)
                        logger.info(
                            f"thread context for engagement: "
                            f"{len(thread_context)} chars"
                        )
                    except Exception as e:
                        logger.warning(
                            f"failed to fetch thread for engaged post {post_uri}: {e}"
                        )
                else:
                    logger.warning(f"get_posts returned empty for {post_uri}")
            except Exception as e:
                logger.warning(f"failed to fetch engaged post {post_uri}: {e}")

        return {
            "uri": post_uri,
            "cid": cid,
            "reason": notification.reason,
            "author_handle": notification.author.handle,
            "author_did": getattr(notification.author, "did", ""),
            "post_text": post_text,
            "embed_desc": "",
            "image_urls": [],
            "root_uri": root_uri,
            "root_cid": root_cid,
            "thread_uri": thread_uri,
            "thread_context": thread_context,
            "indexed_at": getattr(notification, "indexed_at", "") or "",
        }

    async def _build_follow_entry(self, notification) -> dict:
        """Build the notifications_context entry for a follow."""
        return {
            "uri": notification.uri,
            "cid": "",
            "reason": "follow",
            "author_handle": notification.author.handle,
            "author_did": getattr(notification.author, "did", ""),
            "post_text": "",
            "embed_desc": "",
            "image_urls": [],
            "root_uri": notification.uri,
            "root_cid": "",
            "thread_uri": "",
            "thread_context": "",
            "indexed_at": getattr(notification, "indexed_at", "") or "",
        }

    async def handle_batch(self, notifications: list):
        """Process a batch of unread notifications as one cognitive event.

        - Filters rate-limited authors per-notification (preserves the existing
          fairness behavior — chains still count toward each user's hourly cap).
        - Builds notifications_context with all the data the trusted posting
          tools need to act on URIs.
        - Eagerly fetches stranger lookups for unfamiliar authors in the batch
          and injects them up front (cheap, dedup'd by handle).
        - Calls agent.process_notifications once. Tool calls inside the agent
          run handle all side effects.
        """
        if not notifications:
            return

        # Filter rate-limited authors first; record_mention for the rest
        allowed_notifs = []
        for n in notifications:
            handle = n.author.handle
            if not _limiter.hit(_user_limit, handle):
                logger.warning(f"rate limited @{handle}")
                continue
            bot_status.record_mention()
            allowed_notifs.append(n)

        if not allowed_notifs:
            return

        with logfire.span("handle batch", count=len(allowed_notifs)):
            try:
                # Build notifications_context — one entry per notification
                notifications_context: dict = {}
                image_urls_by_uri: dict[str, list[str]] = {}

                for n in allowed_notifs:
                    reason = n.reason
                    entry: dict | None = None
                    if reason in ("mention", "reply", "quote"):
                        entry = await self._build_post_entry(n)
                    elif reason in ("like", "repost"):
                        entry = await self._build_engagement_entry(n)
                    elif reason == "follow":
                        entry = await self._build_follow_entry(n)
                    else:
                        logger.debug(
                            f"unknown notification reason '{reason}' from @{n.author.handle}"
                        )
                        continue

                    if entry is None:
                        continue
                    notifications_context[entry["uri"]] = entry
                    if entry.get("image_urls"):
                        image_urls_by_uri[entry["uri"]] = entry["image_urls"]

                if not notifications_context:
                    logger.info(
                        "batch had no actionable notifications after building context"
                    )
                    return

                # Eagerly look up unfamiliar authors (deduped by handle)
                author_lookups: dict[str, str] = {}
                unique_handles = {
                    e.get("author_handle")
                    for e in notifications_context.values()
                    if e.get("author_handle")
                }
                for handle in unique_handles:
                    lookup = await self._maybe_lookup_stranger(handle)
                    if lookup:
                        author_lookups[handle] = lookup

                logger.info(
                    f"batch: {len(notifications_context)} items, "
                    f"{len(unique_handles)} unique authors, "
                    f"{len(author_lookups)} stranger lookups"
                )

                # Run the agent once over the whole batch.
                # Side effects happen via tool calls inside the run.
                await self.agent.process_notifications(
                    notifications_context=notifications_context,
                    author_lookups=author_lookups,
                    image_urls_by_uri=image_urls_by_uri or None,
                )
            except Exception as e:
                logger.exception(f"batch handler error: {e}")
                bot_status.record_error()

    async def original_thought(self):
        """Generate and post an original thought if phi has something to say.

        The agent uses the `post` tool inside its run if it decides to post.
        """
        with logfire.span("original thought"):
            recent_posts: list[str] = []
            try:
                # Pull 10 recent top-level posts so the musing agent can scan
                # for duplication across a real history window, not just the
                # last few posts.
                feed = await self.client.get_own_posts(limit=10)
                for item in feed:
                    if hasattr(item.post.record, "text"):
                        recent_posts.append(item.post.record.text)
            except Exception as e:
                logger.warning(f"failed to fetch recent posts for musing: {e}")

            try:
                summary = await self.agent.process_musing(
                    recent_posts=recent_posts or None,
                )
                logger.info(f"original thought: {summary[:200]}")
            except Exception as e:
                logger.exception(f"original thought failed: {e}")

    async def check_relays(self):
        """Run a scheduled relay-fleet check and let phi decide whether to post."""
        with logfire.span("relay check"):
            recent_posts: list[str] = []
            try:
                # Pass phi's recent posts so the agent can avoid restating
                # what it already reported.
                feed = await self.client.get_own_posts(limit=10)
                for item in feed:
                    if hasattr(item.post.record, "text"):
                        recent_posts.append(item.post.record.text)
            except Exception as e:
                logger.warning(f"failed to fetch recent posts for relay check: {e}")

            try:
                summary = await self.agent.process_relay_check(
                    recent_posts=recent_posts or None,
                )
                logger.info(f"relay check: {summary[:200]}")
            except Exception as e:
                logger.exception(f"relay check failed: {e}")

    async def review_memories(self):
        """Run the dream/distill pass — review observations with distance."""
        with logfire.span("memory review"):
            try:
                summary = await self.agent.process_review()
                logger.info(f"memory review: {summary}")
            except Exception as e:
                logger.warning(f"memory review failed: {e}")

    async def daily_reflection(self):
        """Generate and post a daily reflection if phi has something to say.

        The agent uses the `post` tool inside its run if it decides to post.
        """
        with logfire.span("daily reflection"):
            # First: review unprocessed interactions and extract observations
            try:
                extracted = await self.agent.process_extraction()
                if extracted:
                    logger.info(f"daily reflection: extracted {extracted} observations")
            except Exception as e:
                logger.warning(f"extraction during reflection failed: {e}")

            # Fetch the last 10 top-level posts so the reflection agent can
            # scan ALL of them for duplication, not just the most recent one.
            # Earlier this fetched limit=1, which let phi correctly avoid
            # duplicating her newest post but blindly duplicate older ones.
            recent_posts: list[str] = []
            try:
                feed = await self.client.get_own_posts(limit=10)
                for item in feed:
                    if hasattr(item.post.record, "text"):
                        recent_posts.append(item.post.record.text)
            except Exception as e:
                logger.warning(f"failed to fetch recent posts for reflection: {e}")

            try:
                summary = await self.agent.process_reflection(
                    recent_posts=recent_posts or None
                )
                logger.info(f"daily reflection: {summary[:200]}")
            except Exception as e:
                logger.exception(f"daily reflection failed: {e}")
