import asyncio
from typing import Optional

from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.services.message_handler import MessageHandler
from bot.status import bot_status


class NotificationPoller:
    def __init__(self, client: BotClient):
        self.client = client
        self.handler = MessageHandler(client)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_seen_at: Optional[str] = None
        self._processed_uris: set[str] = set()  # Track processed notifications

    async def start(self) -> asyncio.Task:
        """Start polling for notifications"""
        self._running = True
        bot_status.polling_active = True
        self._task = asyncio.create_task(self._poll_loop())
        return self._task

    async def stop(self):
        """Stop polling"""
        self._running = False
        bot_status.polling_active = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self):
        """Main polling loop"""
        await self.client.authenticate()

        while self._running:
            try:
                await self._check_notifications()
            except Exception as e:
                print(f"Error in notification poll: {e}")
                bot_status.record_error()
                if settings.debug:
                    import traceback

                    traceback.print_exc()

            # Use wait_for to make shutdown more responsive
            try:
                await asyncio.sleep(settings.notification_poll_interval)
            except asyncio.CancelledError:
                print("📭 Notification poller shutting down gracefully")
                break

    async def _check_notifications(self):
        """Check and process new notifications"""
        # Capture timestamp BEFORE fetching (Void's approach)
        check_time = self.client.client.get_current_time_iso()

        response = await self.client.get_notifications()
        notifications = response.notifications

        if not notifications:
            return

        print(f"📬 Found {len(notifications)} notifications")

        # Count unread mentions
        unread_mentions = [
            n for n in notifications if not n.is_read and n.reason == "mention"
        ]
        if unread_mentions:
            print(f"  → {len(unread_mentions)} unread mentions")

        # Track if we processed any mentions
        processed_any_mentions = False

        # Process notifications from oldest to newest
        for notification in reversed(notifications):
            # Skip if already seen or processed
            if notification.is_read or notification.uri in self._processed_uris:
                continue

            if notification.reason == "mention":
                # Only process mentions
                self._processed_uris.add(notification.uri)
                await self.handler.handle_mention(notification)
                processed_any_mentions = True

        # Mark all notifications as seen using the initial timestamp
        # This ensures we don't miss any that arrived during processing
        if processed_any_mentions:
            await self.client.mark_notifications_seen(check_time)
            print(f"✓ Marked all notifications as read (timestamp: {check_time})")

            # Clean up old processed URIs to prevent memory growth
            # Keep only the last 1000 processed URIs
            if len(self._processed_uris) > 1000:
                # Convert to list, sort by insertion order (oldest first), keep last 500
                self._processed_uris = set(list(self._processed_uris)[-500:])
