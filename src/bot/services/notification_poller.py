"""Simplified notification poller."""

import asyncio
import logging

from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.services.message_handler import MessageHandler
from bot.status import bot_status

logger = logging.getLogger("bot.poller")


class NotificationPoller:
    """Polls for and processes Bluesky notifications."""

    def __init__(self, client: BotClient):
        self.client = client
        self.handler = MessageHandler(client)
        self._running = False
        self._task: asyncio.Task | None = None
        self._processed_uris: set[str] = set()
        self._first_poll = True

    async def start(self) -> asyncio.Task:
        """Start polling for notifications."""
        self._running = True
        bot_status.polling_active = True
        self._task = asyncio.create_task(self._poll_loop())
        return self._task

    async def stop(self):
        """Stop polling."""
        self._running = False
        bot_status.polling_active = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

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

        processed_any = False

        # Process notifications from oldest to newest
        for notification in reversed(notifications):
            if notification.is_read or notification.uri in self._processed_uris:
                continue

            self._processed_uris.add(notification.uri)
            await self.handler.handle_notification(notification)
            processed_any = True

        # Mark all notifications as seen
        if processed_any:
            await self.client.mark_notifications_seen(check_time)
            logger.info("marked notifications as read")

            # Clean up old processed URIs to prevent memory growth
            if len(self._processed_uris) > 1000:
                self._processed_uris = set(list(self._processed_uris)[-500:])
