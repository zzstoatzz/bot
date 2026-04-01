import logging
from pathlib import Path

from atproto import Client, Session, SessionEvent
from atproto_client import models

from bot.config import settings
from bot.core.rich_text import create_facets

logger = logging.getLogger("bot.atproto_client")

SESSION_FILE = Path(".session")


def _get_session_string() -> str | None:
    """Load session from disk if it exists."""
    try:
        if SESSION_FILE.exists():
            return SESSION_FILE.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"failed to load session: {e}")
    return None


def _save_session_string(session_string: str) -> None:
    """Save session to disk."""
    try:
        SESSION_FILE.write_text(session_string, encoding="utf-8")
        logger.debug("session saved to disk")
    except Exception as e:
        logger.warning(f"failed to save session: {e}")


def _on_session_change(event: SessionEvent, session: Session) -> None:
    """Handle session changes (creation and refresh)."""
    if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
        logger.debug(f"session {event.value}, saving to disk")
        _save_session_string(session.export())


MAX_GRAPHEMES = 300


def _split_text(text: str, max_len: int = MAX_GRAPHEMES) -> list[str]:
    """Split text into chunks that fit within bluesky's grapheme limit.

    Prefers splitting at paragraph breaks, then sentence boundaries, then word boundaries.
    """
    if len(text) <= max_len:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        # scan backwards from limit for best break point
        split_at = -1

        # prefer paragraph break (newline)
        for i in range(max_len - 1, max_len // 2, -1):
            if remaining[i] == "\n":
                split_at = i + 1
                break

        # then sentence boundary (.!?) followed by space or end
        if split_at < 0:
            for i in range(max_len - 1, max_len // 2, -1):
                if remaining[i] in ".!?" and (
                    i + 1 >= len(remaining) or remaining[i + 1] in " \n"
                ):
                    split_at = i + 1
                    break

        # then word boundary
        if split_at < 0:
            split_at = remaining.rfind(" ", 0, max_len)
            if split_at < max_len // 2:
                split_at = max_len  # hard break as last resort

        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    return chunks


class BotClient:
    def __init__(self):
        self.client = Client(base_url=settings.bluesky_service)
        self.client.on_session_change(_on_session_change)
        self._authenticated = False

    async def authenticate(self):
        """Authenticate with Bluesky, reusing session if available."""
        if self._authenticated:
            return

        # Try to reuse existing session first
        session_string = _get_session_string()
        if session_string:
            try:
                logger.info("reusing saved session")
                self.client.login(session_string=session_string)
                self._authenticated = True
                logger.info("session restored")
                return
            except Exception as e:
                logger.warning(f"failed to reuse session: {e}, creating new one")
                # Delete invalid session file
                if SESSION_FILE.exists():
                    SESSION_FILE.unlink()

        # Create new session if no valid session exists
        logger.info("creating new session")
        self.client.login(settings.bluesky_handle, settings.bluesky_password)
        self._authenticated = True
        logger.info("new session created")

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
        """Create a new post or reply. Splits long text into a self-reply thread."""
        await self.authenticate()

        if len(text) <= 300:
            facets = create_facets(text, self.client)
            if reply_to:
                return self.client.send_post(
                    text=text, reply_to=reply_to, facets=facets
                )
            return self.client.send_post(text=text, facets=facets)

        chunks = _split_text(text)
        root_ref = reply_to.root if reply_to else None
        last_result = None

        for i, chunk in enumerate(chunks):
            facets = create_facets(chunk, self.client)

            if i == 0:
                last_result = self.client.send_post(
                    text=chunk, reply_to=reply_to, facets=facets
                )
                if root_ref is None:
                    root_ref = models.ComAtprotoRepoStrongRef.Main(
                        uri=last_result.uri, cid=last_result.cid
                    )
            else:
                parent_ref = models.ComAtprotoRepoStrongRef.Main(
                    uri=last_result.uri, cid=last_result.cid
                )
                thread_ref = models.AppBskyFeedPost.ReplyRef(
                    parent=parent_ref, root=root_ref
                )
                last_result = self.client.send_post(
                    text=chunk, reply_to=thread_ref, facets=facets
                )

        return last_result

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

    async def get_own_posts(self, limit: int = 10):
        """Fetch the bot's own recent posts (top-level only, no replies)."""
        await self.authenticate()
        response = self.client.app.bsky.feed.get_author_feed(
            params={
                "actor": self.client.me.did,
                "limit": limit,
                "filter": "posts_no_replies",
            }
        )
        return response.feed

    async def get_timeline(self, limit: int = 25):
        """Fetch the 'following' timeline feed."""
        await self.authenticate()
        return self.client.app.bsky.feed.get_timeline(params={"limit": limit})

    async def get_feed(self, feed_uri: str, limit: int = 25):
        """Fetch posts from a custom feed by AT-URI."""
        await self.authenticate()
        return self.client.app.bsky.feed.get_feed(
            params={"feed": feed_uri, "limit": limit}
        )

    async def follow_user(self, handle: str) -> str:
        """Resolve handle to DID and create a follow record. Returns the record URI."""
        await self.authenticate()
        resolved = self.client.resolve_handle(handle)
        response = self.client.follow(resolved.did)
        return response.uri

    async def get_following(self, limit: int = 100):
        """Get accounts the bot is following."""
        await self.authenticate()
        return self.client.app.bsky.graph.get_follows(
            params={"actor": self.client.me.did, "limit": limit}
        )


bot_client: BotClient = BotClient()
