"""Feed tools — timeline and feed reading, following."""

import logging

from pydantic_ai import RunContext

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.override import get_override, refusal_text
from bot.core.prior_coverage import coverage_note
from bot.tools._helpers import PhiDeps, _format_feed_posts, _is_owner

logger = logging.getLogger("bot.tools.feeds")


def register(agent):
    @agent.tool
    async def read_feed(
        ctx: RunContext[PhiDeps], name: str = "timeline", limit: int = 20
    ) -> str:
        """Read posts from a feed.

        name: 'timeline' (default) for your following timeline — posts from
        accounts you follow; a saved feed name (e.g. 'for-you'); or one of
        your own feed slugs.
        """
        try:
            if name == "timeline":
                response = await bot_client.get_timeline(limit=limit)
                if not response.feed:
                    return (
                        "your timeline is empty — you're not following anyone yet. "
                        f"ask @{settings.owner_handle} to have me follow some accounts!"
                    )
                result = _format_feed_posts(response.feed, limit=limit)
                # perception-keyed recall: seeing the material reminds you
                # that you already covered it.
                if note := await coverage_note(ctx.deps.memory, result):
                    result += f"\n\n{note}"
                return result

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
            result = _format_feed_posts(response.feed, limit=limit)
            if note := await coverage_note(ctx.deps.memory, result):
                result += f"\n\n{note}"
            return result
        except Exception as e:
            return f"failed to read feed: {e}"

    @agent.tool(metadata={"operator_only": True})
    async def follow_user(
        ctx: RunContext[PhiDeps], handle: str, subscribe_posts: bool = False
    ) -> str:
        """Follow a user on bluesky. Only the bot's owner can use this tool.

        Pass subscribe_posts=True to ALSO subscribe to the account's posts —
        their new top-level posts then arrive in your notifications instead of
        waiting for a timeline read. Right for official sources you must not
        miss (e.g. a market's exchange account); wrong for ordinary friends.
        """
        if not _is_owner(ctx):
            return f"only @{settings.owner_handle} can ask me to follow people"
        override = await get_override()
        if override["active"]:
            return refusal_text(override)
        try:
            # check if already following
            already = False
            following = await bot_client.get_following()
            for f in following.follows:
                if f.handle == handle:
                    if not subscribe_posts:
                        return f"already following @{handle}"
                    already = True
                    break
            uri = await bot_client.follow_user(handle, subscribe_posts=subscribe_posts)
            base = f"now following @{handle}" if not already else f"@{handle}"
            sub = " + subscribed to their posts" if subscribe_posts else ""
            return f"{base}{sub} ({uri})"
        except Exception as e:
            return f"failed to follow @{handle}: {e}"
