"""Message handler using MCP-enabled agent."""

import logging

import logfire
from atproto_client import models
from limits import parse as parse_limit
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from bot.agent import PhiAgent
from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.status import bot_status
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


async def _allowed_handles(*extra: str) -> set[str]:
    """Build the set of handles phi may tag (create mention facets for).

    Always includes the bot owner, the bot itself, and anyone who has
    opted in (stored on PDS).  Pass conversation participants as *extra*.
    """
    from bot.core.mentionable import get_mentionable_handles

    base = {settings.owner_handle, settings.bluesky_handle}
    try:
        base.update(await get_mentionable_handles())
    except Exception:
        logger.warning("failed to load mentionable handles from PDS, using base set")
    return base | {h for h in extra if h}


class MessageHandler:
    """Handles incoming notifications using phi agent."""

    def __init__(self, client: BotClient):
        self.client = client
        self.agent = PhiAgent()

    async def handle_notification(self, notification):
        """Process any notification through the agent."""
        reason = notification.reason
        author_handle = notification.author.handle

        if not _limiter.hit(_user_limit, author_handle):
            logger.warning(f"rate limited @{author_handle}")
            return

        with logfire.span(
            "handle notification",
            reason=reason,
            author=author_handle,
        ):
            try:
                if reason in ("mention", "reply", "quote"):
                    await self._handle_post(notification)
                elif reason in ("like", "repost"):
                    await self._handle_engagement(notification)
                elif reason == "follow":
                    await self._handle_follow(notification)
                else:
                    logger.debug(f"notification type '{reason}' from @{author_handle}")
            except Exception as e:
                logger.exception(f"notification handling error: {e}")
                bot_status.record_error()

    async def _handle_engagement(self, notification):
        """Process a like or repost — someone engaged with phi's content."""
        reason = notification.reason
        author_handle = notification.author.handle
        post_uri = notification.uri

        # Fetch phi's post that was liked/reposted
        posts = await self.client.get_posts([post_uri])
        if not posts.posts:
            logger.warning(f"could not find post {post_uri}")
            return

        post = posts.posts[0]
        post_text = post.record.text if hasattr(post.record, "text") else ""

        bot_status.record_mention()

        mention_text = f"[notification: @{author_handle} {reason}d your post]\nyour post: {post_text}"

        response = await self.agent.process_mention(
            mention_text=mention_text,
            author_handle=author_handle,
            thread_context="",
        )

        if response.action == "ignore":
            logger.info(f"ignoring {reason} from @{author_handle}: {response.reason}")
        elif response.action == "reply" and response.text:
            # reply to phi's own post as a follow-up
            parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=post_uri, cid=post.cid)
            if hasattr(post.record, "reply") and post.record.reply:
                root_ref = post.record.reply.root
            else:
                root_ref = parent_ref
            reply_ref = models.AppBskyFeedPost.ReplyRef(
                parent=parent_ref, root=root_ref
            )
            allowed = await _allowed_handles(author_handle)
            await self.client.create_post(
                response.text, reply_to=reply_ref, allowed_handles=allowed
            )
            bot_status.record_response()
            logger.info(
                f"replied on {reason} from @{author_handle}: {response.text[:80]}"
            )
        else:
            logger.info(f"{response.action} on {reason} from @{author_handle}")
            bot_status.record_response()

    async def _handle_follow(self, notification):
        """Process a follow notification."""
        author_handle = notification.author.handle

        bot_status.record_mention()

        mention_text = f"[notification: @{author_handle} followed you]"

        response = await self.agent.process_mention(
            mention_text=mention_text,
            author_handle=author_handle,
            thread_context="",
        )

        if response.action == "ignore":
            logger.info(f"ignoring follow from @{author_handle}: {response.reason}")
        elif response.action == "reply" and response.text:
            # post as a top-level post since there's no thread to reply to
            allowed = await _allowed_handles(author_handle)
            await self.client.create_post(response.text, allowed_handles=allowed)
            bot_status.record_response()
            logger.info(f"posted on follow from @{author_handle}: {response.text[:80]}")
        else:
            logger.info(f"{response.action} on follow from @{author_handle}")

    async def _handle_post(self, notification):
        """Process a mention, reply, or quote notification."""
        post_uri = notification.uri

        # Get the post
        posts = await self.client.get_posts([post_uri])
        if not posts.posts:
            logger.warning(f"could not find post {post_uri}")
            return

        post = posts.posts[0]
        mention_text = resolve_facet_links(post.record)
        author_handle = post.author.handle

        # Include embed content (images, links, quote posts) in the mention
        embed = post.embed if hasattr(post, "embed") and post.embed else None
        if not embed and hasattr(post.record, "embed") and post.record.embed:
            embed = post.record.embed

        embed_desc = describe_embed(embed) if embed else None
        if embed_desc:
            mention_text = f"{mention_text}\n{embed_desc}"

        # Extract image URLs for multimodal vision
        image_urls = extract_image_urls(embed) if embed else []

        bot_status.record_mention()

        # Build reply reference
        parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=post_uri, cid=post.cid)

        # Check if this is part of a thread
        if hasattr(post.record, "reply") and post.record.reply:
            root_ref = post.record.reply.root
            thread_uri = root_ref.uri
        else:
            root_ref = parent_ref
            thread_uri = post_uri

        # Fetch thread context directly from network
        thread_context = "No previous messages in this thread."
        try:
            logger.debug(f"fetching thread context for {thread_uri}")
            thread_data = await self.client.get_thread(thread_uri, depth=100)
            thread_context = build_thread_context(thread_data.thread)
        except Exception as e:
            logger.warning(f"failed to fetch thread context: {e}")

        # Process with agent (has episodic memory + MCP tools)
        response = await self.agent.process_mention(
            mention_text=mention_text,
            author_handle=author_handle,
            thread_context=thread_context,
            thread_uri=thread_uri,
            image_urls=image_urls,
        )

        # Handle response actions
        if response.action == "ignore":
            logger.info(f"ignoring @{author_handle}: {response.reason}")
            return

        elif response.action == "like":
            await self.client.like_post(uri=post_uri, cid=post.cid)
            logger.info(f"liked @{author_handle}")
            bot_status.record_response()
            return

        elif response.action == "repost":
            await self.client.repost(uri=post_uri, cid=post.cid)
            logger.info(f"reposted @{author_handle}")
            bot_status.record_response()
            return

        elif response.action == "reply" and response.text:
            reply_ref = models.AppBskyFeedPost.ReplyRef(
                parent=parent_ref, root=root_ref
            )
            allowed = await _allowed_handles(author_handle)
            await self.client.create_post(
                response.text, reply_to=reply_ref, allowed_handles=allowed
            )

            bot_status.record_response()
            logger.info(f"replied to @{author_handle}: {response.text[:80]}")

    async def original_thought(self):
        """Generate and post an original thought if phi has something to say."""
        with logfire.span("original thought"):
            # Fetch recent posts so the agent can avoid repetition
            recent_posts: list[str] = []
            try:
                feed = await self.client.get_own_posts(limit=5)
                for item in feed:
                    if hasattr(item.post.record, "text"):
                        recent_posts.append(item.post.record.text)
            except Exception as e:
                logger.warning(f"failed to fetch recent posts for musing: {e}")

            try:
                response = await self.agent.process_musing(
                    recent_posts=recent_posts or None
                )
            except Exception as e:
                logger.exception(f"original thought failed: {e}")
                return

            if response.action in ("reply", "post") and response.text:
                try:
                    allowed = await _allowed_handles()
                    await self.client.create_post(
                        response.text, allowed_handles=allowed
                    )
                    bot_status.record_response()
                    logger.info(f"original thought posted: {response.text[:80]}")
                except Exception as e:
                    logger.exception(f"failed to post original thought: {e}")
            else:
                logger.info(f"original thought: nothing to say ({response.reason})")

    async def daily_reflection(self):
        """Generate and post a daily reflection if phi has something to say."""
        with logfire.span("daily reflection"):
            # First: review unprocessed interactions and extract observations
            try:
                extracted = await self.agent.process_extraction()
                if extracted:
                    logger.info(f"daily reflection: extracted {extracted} observations")
            except Exception as e:
                logger.warning(f"extraction during reflection failed: {e}")

            # Fetch last top-level post so the agent knows what it said recently
            last_post_text = None
            try:
                feed = await self.client.get_own_posts(limit=1)
                if feed:
                    last_post_text = feed[0].post.record.text
            except Exception as e:
                logger.warning(f"failed to fetch last post for reflection: {e}")

            try:
                response = await self.agent.process_reflection(
                    last_post_text=last_post_text
                )
            except Exception as e:
                logger.exception(f"daily reflection failed: {e}")
                return

            if response.action in ("reply", "post") and response.text:
                try:
                    allowed = await _allowed_handles()
                    await self.client.create_post(
                        response.text, allowed_handles=allowed
                    )
                    bot_status.record_response()
                    logger.info(f"daily reflection posted: {response.text[:80]}")
                except Exception as e:
                    logger.exception(f"failed to post daily reflection: {e}")
            else:
                logger.info(f"daily reflection: nothing to say ({response.reason})")
