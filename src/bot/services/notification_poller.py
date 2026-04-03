"""Simplified notification poller."""

import asyncio
import logging
from datetime import UTC, date, datetime

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

    async def _poll_loop(self):
        """Main polling loop."""
        await self.client.authenticate()

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
                await asyncio.sleep(settings.notification_poll_interval)
            except asyncio.CancelledError:
                logger.info("notification poller shutting down")
                raise

    async def _check_notifications(self):
        """Check and process new notifications."""
        check_time = self.client.client.get_current_time_iso()

        response = await self.client.get_notifications()
        notifications = response.notifications

        unread = [n for n in notifications if not n.is_read]

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

        dispatched = 0

        # Dispatch notifications as concurrent background tasks
        for notification in reversed(notifications):
            if notification.is_read or notification.uri in self._processed_uris:
                continue

            self._processed_uris.add(notification.uri)
            task = asyncio.create_task(self._handle_with_semaphore(notification))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            dispatched += 1

        # Mark as read immediately — don't wait for processing
        if dispatched:
            await self.client.mark_notifications_seen(check_time)
            logger.info(f"dispatched {dispatched} notifications, marked as read")

            if len(self._processed_uris) > 1000:
                self._processed_uris = set(list(self._processed_uris)[-500:])

    async def _handle_with_semaphore(self, notification):
        """Handle a single notification with concurrency limiting."""
        async with self._semaphore:
            try:
                await self.handler.handle_notification(notification)
            except Exception as e:
                logger.error(
                    f"notification handler error: {e}", exc_info=settings.debug
                )
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
