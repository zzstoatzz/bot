import asyncio
import logging
import time

from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.services.message_handler import MessageHandler
from bot.status import bot_status

logger = logging.getLogger("bot.poller")


class NotificationPoller:
    def __init__(self, client: BotClient):
        self.client = client
        self.handler = MessageHandler(client)
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_seen_at: str | None = None
        self._processed_uris: set[str] = set()  # Track processed notifications
        self._first_poll = True  # Track if this is our first check
        self._notified_approval_ids: set[int] = set()  # Track approvals we've notified about
        self._processed_dm_ids: set[str] = set()  # Track DMs we've already processed

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
                logger.error(f"Error in notification poll: {e}")
                bot_status.record_error()
                if settings.debug:
                    import traceback

                    traceback.print_exc()

            # Sleep with proper cancellation handling
            try:
                await asyncio.sleep(settings.notification_poll_interval)
            except asyncio.CancelledError:
                logger.info("📭 Notification poller shutting down gracefully")
                raise  # Re-raise to properly propagate cancellation

    async def _check_notifications(self):
        """Check and process new notifications"""
        # Capture timestamp BEFORE fetching (Void's approach)
        check_time = self.client.client.get_current_time_iso()

        response = await self.client.get_notifications()
        notifications = response.notifications
        
        # Also check for DM approvals periodically
        await self._check_dm_approvals()

        # Count unread mentions and replies
        unread_mentions = [
            n
            for n in notifications
            if not n.is_read and n.reason in ["mention", "reply"]
        ]

        # First poll: show initial state
        if self._first_poll:
            self._first_poll = False
            if notifications:
                logger.info(
                    f"📬 Found {len(notifications)} notifications ({len(unread_mentions)} unread mentions)"
                )
        # Subsequent polls: only show activity
        elif unread_mentions:
            logger.info(f"📬 {len(unread_mentions)} new mentions")
        else:
            # In debug mode, be silent about empty polls
            # In production, we could add a subtle indicator
            pass

        # Track if we processed any mentions
        processed_any_mentions = False

        # Process notifications from oldest to newest
        for notification in reversed(notifications):
            # Skip if already seen or processed
            if notification.is_read or notification.uri in self._processed_uris:
                logger.debug(f"⏭️  Skipping already processed: {notification.uri}")
                continue

            logger.debug(f"🔍 Found notification: reason={notification.reason}, uri={notification.uri}")
            
            if notification.reason in ["mention", "reply"]:
                # Process mentions and replies in threads
                self._processed_uris.add(notification.uri)
                await self.handler.handle_mention(notification)
                processed_any_mentions = True
            else:
                logger.debug(f"⏭️  Ignoring notification type: {notification.reason}")

        # Mark all notifications as seen using the initial timestamp
        # This ensures we don't miss any that arrived during processing
        if processed_any_mentions:
            await self.client.mark_notifications_seen(check_time)
            logger.info("✓ Marked all notifications as read")

            # Clean up old processed URIs to prevent memory growth
            # Keep only the last 1000 processed URIs
            if len(self._processed_uris) > 1000:
                # Convert to list, sort by insertion order (oldest first), keep last 500
                self._processed_uris = set(list(self._processed_uris)[-500:])
    
    async def _check_dm_approvals(self):
        """Check DMs for approval responses and process approved changes"""
        try:
            from bot.core.dm_approval import process_dm_for_approval, check_pending_approvals, notify_operator_of_pending
            from bot.personality import process_approved_changes
            
            # Check if we have pending approvals
            pending = check_pending_approvals()
            if not pending:
                return
            
            logger.debug(f"Checking DMs for {len(pending)} pending approvals")
            
            # Get recent DMs
            chat_client = self.client.client.with_bsky_chat_proxy()
            convos = chat_client.chat.bsky.convo.list_convos()
            
            # Check each conversation for approval messages
            for convo in convos.convos:
                # Look for messages from operator
                messages = chat_client.chat.bsky.convo.get_messages(
                    params={"convoId": convo.id, "limit": 5}
                )
                
                for msg in messages.messages:
                    # Skip if we've already processed this message
                    if msg.id in self._processed_dm_ids:
                        continue
                    
                    # Skip if not from a member of the conversation
                    sender_handle = None
                    for member in convo.members:
                        if member.did == msg.sender.did:
                            sender_handle = member.handle
                            break
                    
                    if sender_handle:
                        logger.debug(f"DM from @{sender_handle}: {msg.text[:50]}...")
                        # Mark this message as processed
                        self._processed_dm_ids.add(msg.id)
                        
                        # Process any approval/denial in the message
                        processed = await process_dm_for_approval(
                            msg.text, 
                            sender_handle,
                            msg.sent_at
                        )
                        if processed:
                            logger.info(f"Processed {len(processed)} approvals from DM")
                            # Remove processed IDs from notified set
                            for approval_id in processed:
                                self._notified_approval_ids.discard(approval_id)
                            
                            # Mark the conversation as read
                            try:
                                chat_client.chat.bsky.convo.update_read(
                                    data={"convoId": convo.id}
                                )
                                logger.debug(f"Marked conversation {convo.id} as read")
                            except Exception as e:
                                logger.warning(f"Failed to mark conversation as read: {e}")
            
            # Process any approved personality changes
            if self.handler.response_generator.memory:
                changes = await process_approved_changes(self.handler.response_generator.memory)
                if changes:
                    logger.info(f"Applied {changes} approved personality changes")
            
            # Notify operator of new pending approvals
            if len(pending) > 0:
                await notify_operator_of_pending(self.client, self._notified_approval_ids)
                # Add all pending IDs to notified set
                for approval in pending:
                    self._notified_approval_ids.add(approval["id"])
                
        except Exception as e:
            logger.warning(f"DM approval check failed: {e}")
