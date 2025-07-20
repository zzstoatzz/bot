from atproto import models
from bot.core.atproto_client import BotClient
from bot.core.response_generator import response_generator


class MessageHandler:
    def __init__(self, client: BotClient):
        self.client = client
    
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
            
            # Generate placeholder response
            reply_text = await response_generator.generate_response(
                mention_text=mention_text,
                author_handle=author_handle
            )
            
            # Build reply reference
            parent_ref = models.ComAtprotoRepoStrongRef.Main(
                uri=post_uri,
                cid=post.cid
            )
            
            # Check if this is part of a thread
            if hasattr(post.record, 'reply') and post.record.reply:
                # Use existing thread root
                root_ref = post.record.reply.root
            else:
                # This post is the root
                root_ref = parent_ref
                
            reply_ref = models.AppBskyFeedPost.ReplyRef(
                parent=parent_ref,
                root=root_ref
            )
            
            # Send the reply
            await self.client.create_post(reply_text, reply_to=reply_ref)
            
            print(f"✅ Replied to @{author_handle}: {reply_text}")
            
        except Exception as e:
            print(f"❌ Error handling mention: {e}")
            import traceback
            traceback.print_exc()