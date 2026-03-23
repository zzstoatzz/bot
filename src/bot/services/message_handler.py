"""Message handler using MCP-enabled agent."""

import logging

from atproto_client import models

from bot.agent import PhiAgent
from bot.core.atproto_client import BotClient
from bot.status import bot_status
from bot.utils.thread import build_thread_context, describe_embed, extract_image_urls

logger = logging.getLogger("bot.handler")


class MessageHandler:
    """Handles incoming mentions using phi agent."""

    def __init__(self, client: BotClient):
        self.client = client
        self.agent = PhiAgent()

    async def handle_mention(self, notification):
        """Process a mention or reply notification."""
        try:
            if notification.reason not in ["mention", "reply"]:
                return

            post_uri = notification.uri

            # Get the post that mentioned us
            posts = await self.client.get_posts([post_uri])
            if not posts.posts:
                logger.warning(f"could not find post {post_uri}")
                return

            post = posts.posts[0]
            mention_text = post.record.text
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
                # Post reply
                reply_ref = models.AppBskyFeedPost.ReplyRef(
                    parent=parent_ref, root=root_ref
                )
                await self.client.create_post(response.text, reply_to=reply_ref)

                bot_status.record_response()
                logger.info(f"replied to @{author_handle}: {response.text[:80]}")

        except Exception as e:
            logger.exception(f"mention handling error: {e}")
            bot_status.record_error()
