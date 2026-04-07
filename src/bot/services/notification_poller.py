"""Simplified notification poller."""

import asyncio
import logging
from datetime import UTC, date, datetime

import logfire

from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.services.message_handler import MessageHandler
from bot.status import bot_status

logger = logging.getLogger("bot.poller")


MAX_CONCURRENT = 3


class NotificationPoller:
    """Polls for and processes Bluesky notifications."""

    def __init__(self, client: BotClient):
        self.client = client
        self.handler = MessageHandler(client)
        self._running = False
        self._task: asyncio.Task | None = None
        self._processed_uris: set[str] = set()
        self._first_poll = True
        self._last_daily_post: datetime | None = None
        self._last_thought_hours: set[int] = set()
        self._last_thought_date: date | None = None
        self._last_exploration_hours: set[int] = set()
        self._last_exploration_date: date | None = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._background_tasks: set[asyncio.Task] = set()

    async def start(self) -> asyncio.Task:
        """Start polling for notifications."""
        self._running = True
        bot_status.polling_active = True
        self._task = asyncio.create_task(self._poll_loop())
        return self._task

    async def stop(self):
        """Stop polling and wait for in-flight handlers to finish."""
        self._running = False
        bot_status.polling_active = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # wait for any in-flight notification handlers
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

    async def _seed_schedule_from_history(self):
        """Seed scheduling state from phi's recent post history.

        Without this, every restart wipes _last_daily_post and
        _last_thought_hours, causing phi to re-run today's daily reflection
        and any thought-post hours that already happened. The fix: at startup,
        look at phi's recent top-level posts and infer which schedule slots
        have already been filled today.

        Heuristic (deliberately loose):
        - any top-level post made today UTC at or after daily_reflection_hour
          marks the daily reflection slot as already done
        - any top-level post made today UTC during a thought_post_hours hour
          marks that hour as already done

        This is approximate — phi makes top-level posts from many contexts
        besides scheduled reflections (e.g. agent replies that decided to go
        top-level). But the worst case of being approximate is that phi
        SKIPS a scheduled post that was actually a reply-shaped post — which
        is the safe failure mode (silence is fine, double-posting is not).
        """
        try:
            feed = await self.client.get_own_posts(limit=20)
        except Exception as e:
            logger.warning(f"failed to seed schedule from history: {e}")
            return

        today = datetime.now(UTC).date()
        seeded_daily = False
        seeded_hours: set[int] = set()

        for item in feed:
            indexed_at = getattr(item.post, "indexed_at", None)
            if not indexed_at:
                continue
            try:
                ts = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if ts.date() != today:
                continue

            if not seeded_daily and ts.hour >= settings.daily_reflection_hour:
                self._last_daily_post = ts
                seeded_daily = True

            if ts.hour in settings.thought_post_hours:
                seeded_hours.add(ts.hour)

        if seeded_hours:
            self._last_thought_hours = seeded_hours
            self._last_thought_date = today

        if seeded_daily or seeded_hours:
            logger.info(
                f"seeded schedule from history: "
                f"daily_done={seeded_daily}, thought_hours={sorted(seeded_hours)}"
            )

    async def _poll_loop(self):
        """Main polling loop."""
        await self.client.authenticate()

        # Restore scheduling state from observed post history so deploys
        # don't cause duplicate scheduled posts.
        await self._seed_schedule_from_history()

        while self._running:
            try:
                await self._check_notifications()
            except Exception as e:
                logger.error(f"notification poll error: {e}", exc_info=settings.debug)
                bot_status.record_error()
                continue

            try:
                if self._should_do_daily_post():
                    task = asyncio.create_task(self._maybe_daily_post())
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            except Exception as e:
                logger.error(f"daily reflection error: {e}", exc_info=settings.debug)

            try:
                if self._should_do_thought_post():
                    task = asyncio.create_task(self._maybe_thought_post())
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            except Exception as e:
                logger.error(f"thought post error: {e}", exc_info=settings.debug)

            try:
                if self._should_do_exploration():
                    task = asyncio.create_task(self._maybe_explore())
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            except Exception as e:
                logger.error(f"exploration error: {e}", exc_info=settings.debug)

            try:
                await asyncio.sleep(settings.notification_poll_interval)
            except asyncio.CancelledError:
                logger.info("notification poller shutting down")
                raise

    async def _check_notifications(self):
        """Check for new notifications and dispatch the whole batch as one task.

        The unit of work is *one poll cycle*. Every unread notification at this
        moment goes into a single batch that the handler processes as one
        cognitive event. This means a chain of replies in a thread, or activity
        across multiple threads, all gets considered together by one agent run
        that decides what (if anything) to do about each item.
        """
        check_time = self.client.client.get_current_time_iso()

        # Wrap the bsky list_notifications call in an observability span so we
        # can see the raw response — counts AND the actual unread items.
        # Without this we only see phi's downstream interpretation (post-filter
        # batch size), which makes "why did bsky return only N" unanswerable
        # from logs alone.
        with logfire.span("fetch notifications", check_time=check_time) as fetch_span:
            response = await self.client.get_notifications()
            notifications = response.notifications

            unread = [n for n in notifications if not n.is_read]

            fetch_span.set_attribute("total_count", len(notifications))
            fetch_span.set_attribute("unread_count", len(unread))
            if unread:
                # Capture each unread entry as a structured dict so we can
                # answer questions like "did bsky return all 3 mentions or
                # just 1" without re-running the test.
                fetch_span.set_attribute(
                    "unread_items",
                    [
                        {
                            "uri": n.uri,
                            "cid": getattr(n, "cid", "") or "",
                            "author_handle": n.author.handle,
                            "reason": n.reason,
                            "reason_subject": getattr(n, "reason_subject", None) or "",
                            "indexed_at": str(getattr(n, "indexed_at", "") or ""),
                            "is_read": n.is_read,
                        }
                        for n in unread
                    ],
                )

        # First poll: show initial state
        if self._first_poll:
            self._first_poll = False
            if notifications:
                logger.info(
                    f"found {len(notifications)} notifications ({len(unread)} unread)"
                )
        elif unread:
            logger.info(f"{len(unread)} new notifications")

        # When paused, don't process or mark as read — notifications accumulate
        if bot_status.paused:
            if unread:
                logger.debug(f"paused, skipping {len(unread)} unread notifications")
            return

        # Build the batch from unread notifications phi hasn't already processed
        batch = [n for n in unread if n.uri not in self._processed_uris]
        if not batch:
            return

        for n in batch:
            self._processed_uris.add(n.uri)

        # Dispatch the entire batch as one task — one cognitive event per poll
        task = asyncio.create_task(self._handle_batch_with_semaphore(batch))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Mark notifications as seen on bsky immediately — don't wait for processing
        await self.client.mark_notifications_seen(check_time)
        logger.info(f"dispatched batch of {len(batch)} notifications, marked as read")

        if len(self._processed_uris) > 1000:
            self._processed_uris = set(list(self._processed_uris)[-500:])

    async def _handle_batch_with_semaphore(self, batch: list):
        """Handle a notification batch with concurrency limiting."""
        async with self._semaphore:
            try:
                await self.handler.handle_batch(batch)
            except Exception as e:
                logger.error(f"batch handler error: {e}", exc_info=settings.debug)
                bot_status.record_error()

    def _should_do_daily_post(self) -> bool:
        """Check if it's time for a daily reflection."""
        now = datetime.now(UTC)
        if now.hour < settings.daily_reflection_hour:
            return False
        if bot_status.paused:
            return False
        if self._last_daily_post and self._last_daily_post.date() == now.date():
            return False
        return True

    async def _maybe_daily_post(self):
        """Post a daily reflection."""
        self._last_daily_post = datetime.now(UTC)
        logger.info("triggering daily reflection")
        try:
            await self.handler.daily_reflection()
        except Exception as e:
            logger.error(f"daily reflection error: {e}", exc_info=settings.debug)

    def _should_do_thought_post(self) -> bool:
        """Check if it's time for an original thought post."""
        now = datetime.now(UTC)
        today = now.date()
        if bot_status.paused:
            return False
        # reset tracked hours at midnight
        if self._last_thought_date != today:
            self._last_thought_hours = set()
            self._last_thought_date = today
        hour = now.hour
        if hour not in settings.thought_post_hours:
            return False
        if hour in self._last_thought_hours:
            return False
        return True

    async def _maybe_thought_post(self):
        """Post an original thought."""
        now = datetime.now(UTC)
        self._last_thought_hours.add(now.hour)
        self._last_thought_date = now.date()
        logger.info("triggering original thought")
        try:
            await self.handler.original_thought()
        except Exception as e:
            logger.error(f"thought post error: {e}", exc_info=settings.debug)

    def _should_do_exploration(self) -> bool:
        """Check if it's time for background exploration."""
        now = datetime.now(UTC)
        today = now.date()
        if bot_status.paused:
            return False
        # reset tracked hours at midnight
        if self._last_exploration_date != today:
            self._last_exploration_hours = set()
            self._last_exploration_date = today
        hour = now.hour
        if hour not in settings.exploration_hours:
            return False
        if hour in self._last_exploration_hours:
            return False
        return True

    async def _maybe_explore(self):
        """Run one background exploration."""
        now = datetime.now(UTC)
        self._last_exploration_hours.add(now.hour)
        self._last_exploration_date = now.date()
        logger.info("triggering background exploration")
        try:
            await self.handler.explore()
        except Exception as e:
            logger.error(f"exploration error: {e}", exc_info=settings.debug)
