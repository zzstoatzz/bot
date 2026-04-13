"""Feed scanner — event source for phi's curiosity queue.

Periodically scans the For You feed for unfamiliar authors and enqueues
them for exploration. Runs as a background task, never blocks notifications.
"""

import logging
from datetime import UTC, datetime

import logfire

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.curiosity_queue import enqueue
from bot.tools._helpers import _format_feed_posts

logger = logging.getLogger("bot.feed_scanner")

# how long before a subject can be re-enqueued (seconds)
COOLDOWN_SECONDS = 86400  # 24h
SEEN_CAP = 500


class FeedScanner:
    """Scans the For You feed and enqueues strangers for exploration."""

    def __init__(self):
        self._seen_uris: set[str] = set()
        self._explored_subjects: dict[str, datetime] = {}
        self._recent_posts: list = []
        self._seeded = False

    async def _seed_cooldowns(self):
        """Seed explored_subjects from completed/failed queue items on PDS."""
        if self._seeded:
            return
        self._seeded = True
        try:
            from bot.core.curiosity_queue import _list_records

            records = await _list_records()
            now = datetime.now(UTC)
            for rec in records:
                val = rec.value
                status = val["status"]
                if status in ("completed", "failed"):
                    subject = val["subject"]
                    updated = val.get("updatedAt") or val.get("createdAt", "")
                    try:
                        ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        ts = now
                    self._explored_subjects[subject] = ts
            if self._explored_subjects:
                logger.info(
                    f"seeded {len(self._explored_subjects)} exploration cooldowns"
                )
        except Exception as e:
            logger.warning(f"failed to seed exploration cooldowns: {e}")

    def _is_on_cooldown(self, subject: str) -> bool:
        """Check if a subject was explored recently enough to skip."""
        last = self._explored_subjects.get(subject)
        if not last:
            return False
        elapsed = (datetime.now(UTC) - last).total_seconds()
        return elapsed < COOLDOWN_SECONDS

    async def scan(self, memory) -> int:
        """Scan For You feed, enqueue strangers with cooldown. Returns count enqueued."""
        await self._seed_cooldowns()

        with logfire.span("feed scan"):
            try:
                await bot_client.authenticate()
                response = await bot_client.get_feed(
                    settings.for_you_feed_uri, limit=20
                )
            except Exception as e:
                logger.warning(f"feed scan failed: {e}")
                return 0

            if not response.feed:
                return 0

            # store for musing context
            self._recent_posts = response.feed

            new_posts = []
            for item in response.feed:
                uri = item.post.uri
                if uri in self._seen_uris:
                    continue
                self._seen_uris.add(uri)
                new_posts.append(item)

            # cap seen set
            if len(self._seen_uris) > SEEN_CAP:
                excess = len(self._seen_uris) - SEEN_CAP
                # remove oldest (arbitrary since set, but prevents unbounded growth)
                for _ in range(excess):
                    self._seen_uris.pop()

            enqueued = 0
            for item in new_posts:
                handle = item.post.author.handle
                if handle == settings.bluesky_handle:
                    continue
                if self._is_on_cooldown(handle):
                    continue
                try:
                    if memory and await memory.is_stranger(handle):
                        ok = await enqueue(
                            kind="explore_handle",
                            subject=handle,
                            source="feed",
                        )
                        if ok:
                            self._explored_subjects[handle] = datetime.now(UTC)
                            enqueued += 1
                except Exception as e:
                    logger.debug(f"feed stranger check failed for @{handle}: {e}")

            if enqueued:
                logger.info(f"feed scan: enqueued {enqueued} strangers")
            return enqueued

    def get_recent_posts_text(self) -> str:
        """Return formatted recent feed posts for musing context injection."""
        if not self._recent_posts:
            return ""
        return _format_feed_posts(self._recent_posts, limit=10)
