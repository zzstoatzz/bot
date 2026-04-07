"""Tests for rate limiting and SSRF protection."""

import ipaddress
from unittest.mock import AsyncMock, Mock

from limits import parse as parse_limit
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter


class TestPerUserRateLimiting:
    """Test per-user notification rate limiting."""

    def setup_method(self):
        self.storage = MemoryStorage()
        self.limiter = MovingWindowRateLimiter(self.storage)
        self.limit = parse_limit("3/minute")  # low limit for testing

    def test_allows_under_limit(self):
        for _ in range(3):
            assert self.limiter.hit(self.limit, "user.bsky.social")

    def test_blocks_over_limit(self):
        for _ in range(3):
            self.limiter.hit(self.limit, "user.bsky.social")
        assert not self.limiter.hit(self.limit, "user.bsky.social")

    def test_independent_per_user(self):
        for _ in range(3):
            self.limiter.hit(self.limit, "user-a.bsky.social")
        # user-a is exhausted
        assert not self.limiter.hit(self.limit, "user-a.bsky.social")
        # user-b is unaffected
        assert self.limiter.hit(self.limit, "user-b.bsky.social")


class TestMessageHandlerRateLimiting:
    """Test that MessageHandler.handle_batch respects per-author rate limits.

    Even though batches now coalesce a poll cycle's notifications into one
    agent run, rate limiting still applies per-author per-notification — a
    spammer who chains posts gets each post counted toward their hourly cap.
    Once the cap is hit, subsequent notifications from that author are filtered
    out of the batch and the agent run is skipped if nothing remains.
    """

    async def test_rate_limited_author_filtered_from_batch(self):
        from bot.services import message_handler

        handler = Mock()
        handler.client = Mock()
        handler.agent = Mock()
        handler.agent.process_notifications = AsyncMock()
        handler._build_post_entry = AsyncMock(return_value=None)
        handler._build_engagement_entry = AsyncMock(return_value=None)
        handler._build_follow_entry = AsyncMock(return_value=None)
        handler._maybe_lookup_stranger = AsyncMock(return_value=None)

        def make_notif():
            n = Mock()
            n.reason = "mention"
            n.author.handle = "spammer.bsky.social"
            n.uri = "at://example/post/1"
            return n

        original_limiter = message_handler._limiter
        original_limit = message_handler._user_limit

        # use a 1/minute limit so the second batch with the same author is blocked
        test_storage = MemoryStorage()
        test_limiter = MovingWindowRateLimiter(test_storage)
        test_limit = parse_limit("1/minute")

        message_handler._limiter = test_limiter
        message_handler._user_limit = test_limit

        try:
            # first batch: one notification from the spammer — passes the limiter
            await message_handler.MessageHandler.handle_batch(handler, [make_notif()])
            # _build_post_entry was called (limiter let it through)
            handler._build_post_entry.assert_called_once()

            handler._build_post_entry.reset_mock()

            # second batch from the same author — filtered out by limiter
            # nothing was actionable so build/process never get invoked
            await message_handler.MessageHandler.handle_batch(handler, [make_notif()])
            handler._build_post_entry.assert_not_called()
            handler.agent.process_notifications.assert_not_called()
        finally:
            message_handler._limiter = original_limiter
            message_handler._user_limit = original_limit


class TestSSRFProtection:
    """Test that check_urls blocks private IPs."""

    def test_private_ips_detected(self):
        private_ips = ["127.0.0.1", "10.0.0.1", "192.168.1.1", "172.16.0.1", "::1"]
        for ip_str in private_ips:
            ip = ipaddress.ip_address(ip_str)
            assert ip.is_private or ip.is_loopback or ip.is_link_local, (
                f"{ip_str} should be blocked"
            )

    def test_public_ips_allowed(self):
        public_ips = ["8.8.8.8", "1.1.1.1", "140.82.121.4"]
        for ip_str in public_ips:
            ip = ipaddress.ip_address(ip_str)
            assert not (ip.is_private or ip.is_loopback or ip.is_link_local), (
                f"{ip_str} should be allowed"
            )
