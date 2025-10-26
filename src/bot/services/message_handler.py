"""Message handler using MCP-enabled agent."""

import logging

from atproto_client import models

from bot.agent import PhiAgent
from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.database import thread_db
from bot.status import bot_status

logger = logging.getLogger("bot.handler")


class MessageHandler:
    """Handles incoming mentions using phi agent."""

    def __init__(self, client: BotClient):
        self.client = client
        self.agent = PhiAgent()

    async def _store_thread_messages(self, thread_node, thread_uri: str):
        """Recursively extract and store all messages from a thread."""
        if not thread_node or not hasattr(thread_node, "post"):
            return

        post = thread_node.post

        # Store this message
        thread_db.add_message(
            thread_uri=thread_uri,
            author_handle=post.author.handle,
            author_did=post.author.did,
            message_text=post.record.text,
            post_uri=post.uri,
        )

        # Recursively store replies
        if hasattr(thread_node, "replies") and thread_node.replies:
            for reply in thread_node.replies:
                await self._store_thread_messages(reply, thread_uri)

        # Also check for parent if this is a reply
        if hasattr(thread_node, "parent") and thread_node.parent:
            await self._store_thread_messages(thread_node.parent, thread_uri)

    async def handle_mention(self, notification):
        """Process a mention or reply notification."""
        try:
            if notification.reason not in ["mention", "reply"]:
                return

            post_uri = notification.uri

            # Get the post that mentioned us
            posts = await self.client.get_posts([post_uri])
            if not posts.posts:
                logger.warning(f"Could not find post {post_uri}")
                return

            post = posts.posts[0]
            mention_text = post.record.text
            author_handle = post.author.handle
            author_did = post.author.did

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

            # Discover thread context if we haven't participated yet
            existing_messages = thread_db.get_thread_messages(thread_uri)
            if not existing_messages:
                # Phi is being tagged into an existing thread - fetch full context
                logger.debug(f"🔍 Discovering thread context for {thread_uri}")
                try:
                    thread_data = await self.client.get_thread(thread_uri, depth=100)
                    # Extract and store all messages from the thread
                    await self._store_thread_messages(thread_data.thread, thread_uri)
                except Exception as e:
                    logger.warning(f"Failed to fetch thread context: {e}")

            # Store the current mention in thread history
            thread_db.add_message(
                thread_uri=thread_uri,
                author_handle=author_handle,
                author_did=author_did,
                message_text=mention_text,
                post_uri=post_uri,
            )

            # Get thread context
            thread_context = thread_db.get_thread_context(thread_uri)

            # Process with agent (has episodic memory + MCP tools)
            response = await self.agent.process_mention(
                mention_text=mention_text,
                author_handle=author_handle,
                thread_context=thread_context,
                thread_uri=thread_uri,
            )

            # Handle response actions
            if response.action == "ignore":
                logger.info(
                    f"🙈 Ignoring notification from @{author_handle} ({response.reason})"
                )
                return

            elif response.action == "like":
                await self.client.like_post(uri=post_uri, cid=post.cid)
                logger.info(f"👍 Liked post from @{author_handle}")
                bot_status.record_response()
                return

            elif response.action == "repost":
                await self.client.repost(uri=post_uri, cid=post.cid)
                logger.info(f"🔁 Reposted from @{author_handle}")
                bot_status.record_response()
                return

            elif response.action == "reply" and response.text:
                # Post reply
                reply_ref = models.AppBskyFeedPost.ReplyRef(
                    parent=parent_ref, root=root_ref
                )
                reply_response = await self.client.create_post(
                    response.text, reply_to=reply_ref
                )

                # Store bot's response in thread history
                if reply_response and hasattr(reply_response, "uri"):
                    thread_db.add_message(
                        thread_uri=thread_uri,
                        author_handle=settings.bluesky_handle,
                        author_did=self.client.me.did if self.client.me else "bot",
                        message_text=response.text,
                        post_uri=reply_response.uri,
                    )

                bot_status.record_response()
                logger.info(f"✅ Replied to @{author_handle}: {response.text[:50]}...")

        except Exception as e:
            logger.error(f"❌ Error handling mention: {e}")
            bot_status.record_error()
            import traceback

            traceback.print_exc()
