"""Feed tools — graze feed CRUD, timeline, following."""

import logging

from pydantic_ai import RunContext

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.graze_client import GrazeClient
from bot.tools._helpers import PhiDeps, _format_feed_posts, _is_owner

logger = logging.getLogger("bot.tools.feeds")


def register(agent, graze_client: GrazeClient):
    @agent.tool
    async def create_feed(
        ctx: RunContext[PhiDeps],
        name: str,
        display_name: str,
        description: str,
        filter_manifest: dict,
    ) -> str:
        """Create a new bluesky feed powered by graze. Only the bot's owner can use this tool.

        name: url-safe slug (e.g. "electronic-music"). becomes the feed rkey.
        display_name: human-readable feed title.
        description: what the feed shows.
        filter_manifest: graze filter DSL (grazer engine operators). key operators:
          - regex_any: ["field", ["term1", "term2"]] — match any term (case-insensitive by default)
          - regex_none: ["field", ["term1", "term2"]] — exclude posts matching any term
          - regex_matches: ["field", "pattern"] — single regex match
          - and: [...filters], or: [...filters] — combine filters
        field is usually "text". example: {"filter": {"and": [{"regex_any": ["text", ["jazz", "bebop"]]}]}}
        """
        if not _is_owner(ctx):
            return f"only @{settings.owner_handle} can create feeds"
        try:
            result = await graze_client.create_feed(
                rkey=name,
                display_name=display_name,
                description=description,
                filter_manifest=filter_manifest,
            )
            return f"feed created: {result['uri']} (algo_id={result['algo_id']})"
        except Exception as e:
            logger.warning(f"create_feed failed: {e}")
            return f"failed to create feed: {e}"

    @agent.tool
    async def list_feeds(ctx: RunContext[PhiDeps]) -> str:
        """List your existing graze-powered feeds. Returns name (slug for read_feed) and algo_id (for delete_feed)."""
        try:
            feeds = await graze_client.list_feeds()
            if not feeds:
                return "no graze feeds found"
            lines = []
            for f in feeds:
                display = f.get("display_name") or f.get("name") or "unnamed"
                algo_id = f.get("id") or f.get("algo_id") or "?"
                uri = f.get("feed_uri") or f.get("uri") or ""
                # extract rkey slug from feed_uri for use with read_feed
                rkey = f.get("record_name") or (uri.rsplit("/", 1)[-1] if uri else "?")
                lines.append(f"- {display} | name={rkey} | algo_id={algo_id}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"list_feeds failed: {e}")
            return f"failed to list feeds: {e}"

    @agent.tool
    async def delete_feed(ctx: RunContext[PhiDeps], algo_id: int) -> str:
        """Delete a graze-powered feed by its algo_id. Only the bot's owner can use this tool.

        algo_id: the numeric id from list_feeds (e.g. 33726).
        This deletes both the graze registration and the PDS feed generator record.
        """
        if not _is_owner(ctx):
            return f"only @{settings.owner_handle} can delete feeds"
        try:
            # find the record_name from graze so we can delete the PDS record too
            feeds = await graze_client.list_feeds()
            record_name = None
            for f in feeds:
                if f.get("id") == algo_id:
                    record_name = f.get("record_name")
                    break

            await graze_client.delete_feed(algo_id)

            # also delete the PDS record if we found the rkey
            if record_name:
                assert bot_client.client.me is not None
                try:
                    bot_client.client.com.atproto.repo.delete_record(
                        data={
                            "repo": bot_client.client.me.did,
                            "collection": "app.bsky.feed.generator",
                            "rkey": record_name,
                        }
                    )
                except Exception as e:
                    logger.warning(f"PDS record delete failed: {e}")

            return f"deleted feed algo_id={algo_id}" + (
                f" and PDS record '{record_name}'" if record_name else ""
            )
        except Exception as e:
            logger.warning(f"delete_feed failed: {e}")
            return f"failed to delete feed: {e}"

    # --- feed consumption + following ---

    @agent.tool
    async def read_timeline(ctx: RunContext[PhiDeps], limit: int = 20) -> str:
        """Read your 'following' timeline — posts from accounts you follow. Use this when someone asks what's on your feed or what people you follow are talking about."""
        try:
            response = await bot_client.get_timeline(limit=limit)
            if not response.feed:
                return (
                    "your timeline is empty — you're not following anyone yet. "
                    f"ask @{settings.owner_handle} to have me follow some accounts!"
                )
            return _format_feed_posts(response.feed, limit=limit)
        except Exception as e:
            return f"failed to read timeline: {e}"

    @agent.tool
    async def read_feed(ctx: RunContext[PhiDeps], name: str, limit: int = 20) -> str:
        """Read posts from a feed by name.

        name: a saved feed name (e.g. "for-you") or one of your own feed slugs.
        use list_feeds to see available names.
        """
        try:
            # check saved feeds first (external feeds mapped by friendly name)
            feed_uri = settings.saved_feeds.get(name)
            if not feed_uri:
                # fall back to phi's own graze-powered feeds
                await bot_client.authenticate()
                assert bot_client.client.me is not None
                feed_uri = (
                    f"at://{bot_client.client.me.did}/app.bsky.feed.generator/{name}"
                )
            response = await bot_client.get_feed(feed_uri, limit=limit)
            if not response.feed:
                return "no posts in this feed yet"
            return _format_feed_posts(response.feed, limit=limit)
        except Exception as e:
            return f"failed to read feed: {e}"

    @agent.tool
    async def follow_user(ctx: RunContext[PhiDeps], handle: str) -> str:
        """Follow a user on bluesky. Only the bot's owner can use this tool."""
        if not _is_owner(ctx):
            return f"only @{settings.owner_handle} can ask me to follow people"
        try:
            # check if already following
            following = await bot_client.get_following()
            for f in following.follows:
                if f.handle == handle:
                    return f"already following @{handle}"
            uri = await bot_client.follow_user(handle)
            return f"now following @{handle} ({uri})"
        except Exception as e:
            return f"failed to follow @{handle}: {e}"
