from atproto import Client

from bot.config import settings
from bot.core.rich_text import create_facets


class BotClient:
    def __init__(self):
        self.client = Client(base_url=settings.bluesky_service)
        self._authenticated = False

    async def authenticate(self):
        """Authenticate with Bluesky using app password"""
        if not self._authenticated:
            self.client.login(settings.bluesky_handle, settings.bluesky_password)
            self._authenticated = True

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    @property
    def me(self):
        """Get current user profile"""
        return self.client.me

    async def get_notifications(self, limit: int = 50):
        """Fetch unread notifications"""
        await self.authenticate()
        return self.client.app.bsky.notification.list_notifications(
            params={"limit": limit}
        )

    async def mark_notifications_seen(self, seen_at: str):
        """Mark notifications as seen up to a certain timestamp"""
        await self.authenticate()
        # Use the params format instead of data
        self.client.app.bsky.notification.update_seen({"seenAt": seen_at})

    async def create_post(self, text: str, reply_to=None):
        """Create a new post or reply with rich text support"""
        await self.authenticate()

        # Create facets for mentions and URLs
        facets = create_facets(text, self.client)
        
        # Use send_post with facets
        if reply_to:
            return self.client.send_post(text=text, reply_to=reply_to, facets=facets)
        else:
            return self.client.send_post(text=text, facets=facets)

    async def get_thread(self, uri: str, depth: int = 10):
        """Get a thread by URI"""
        await self.authenticate()
        return self.client.app.bsky.feed.get_post_thread(
            params={"uri": uri, "depth": depth}
        )

    async def get_posts(self, uris: list[str]):
        """Get multiple posts by URIs"""
        await self.authenticate()
        return self.client.app.bsky.feed.get_posts(params={"uris": uris})

    async def search_users(self, query: str, limit: int = 10):
        """Search for users"""
        await self.authenticate()
        return self.client.app.bsky.actor.search_actors(
            params={"q": query, "limit": limit}
        )

    async def like_post(self, uri: str, cid: str):
        """Like a post"""
        await self.authenticate()
        return self.client.like(uri=uri, cid=cid)

    async def repost(self, uri: str, cid: str):
        """Repost a post"""
        await self.authenticate()
        return self.client.repost(uri=uri, cid=cid)


bot_client: BotClient = BotClient()
