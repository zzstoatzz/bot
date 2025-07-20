from atproto import models

from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.database import thread_db
from bot.response_generator import ResponseGenerator
from bot.status import bot_status


class MessageHandler:
    def __init__(self, client: BotClient):
        self.client = client
        self.response_generator = ResponseGenerator()

    async def handle_mention(self, notification):
        """Process a mention notification"""
        try:
            # Skip if not a mention
            if notification.reason != "mention":
                return

            post_uri = notification.uri

            # Get the post that mentioned us
            posts = await self.client.get_posts([post_uri])
            if not posts.posts:
                print(f"Could not find post {post_uri}")
                return

            post = posts.posts[0]
            mention_text = post.record.text
            author_handle = post.author.handle
            author_did = post.author.did

            # Record mention received
            bot_status.record_mention()

            # Build reply reference
            parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=post_uri, cid=post.cid)

            # Check if this is part of a thread
            if hasattr(post.record, "reply") and post.record.reply:
                # Use existing thread root
                root_ref = post.record.reply.root
                thread_uri = root_ref.uri
            else:
                # This post is the root
                root_ref = parent_ref
                thread_uri = post_uri

            # Store the message in thread history
            thread_db.add_message(
                thread_uri=thread_uri,
                author_handle=author_handle,
                author_did=author_did,
                message_text=mention_text,
                post_uri=post_uri,
            )

            # Get thread context
            thread_context = thread_db.get_thread_context(thread_uri)

            # Generate response
            # Note: We pass the full text including @mention
            # In AT Protocol, mentions are structured as facets,
            # but the text representation includes them
            reply_text = await self.response_generator.generate(
                mention_text=mention_text,
                author_handle=author_handle,
                thread_context=thread_context,
            )

            reply_ref = models.AppBskyFeedPost.ReplyRef(
                parent=parent_ref, root=root_ref
            )

            # Send the reply
            response = await self.client.create_post(reply_text, reply_to=reply_ref)

            # Store bot's response in thread history
            if response and hasattr(response, "uri"):
                thread_db.add_message(
                    thread_uri=thread_uri,
                    author_handle=settings.bluesky_handle,
                    author_did=self.client.me.did if self.client.me else "bot",
                    message_text=reply_text,
                    post_uri=response.uri,
                )

            # Record successful response
            bot_status.record_response()

            print(f"✅ Replied to @{author_handle}: {reply_text}")

        except Exception as e:
            print(f"❌ Error handling mention: {e}")
            bot_status.record_error()
            import traceback

            traceback.print_exc()
