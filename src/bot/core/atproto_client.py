from atproto import Client

from bot.config import settings


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
        """Create a new post or reply using the simpler send_post method"""
        await self.authenticate()

        # Use the client's send_post method which handles all the details
        if reply_to:
            # Build proper reply reference if needed
            return self.client.send_post(text=text, reply_to=reply_to)
        else:
            return self.client.send_post(text=text)

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


bot_client = BotClient()
