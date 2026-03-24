"""Tests for rate limiting and SSRF protection."""

import ipaddress
import socket
from unittest.mock import AsyncMock, Mock, patch

import pytest
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
    """Test that MessageHandler.handle_notification respects rate limits."""

    async def test_rate_limited_notification_returns_early(self):
        from bot.services import message_handler

        handler = Mock()
        handler.client = Mock()
        handler.agent = Mock()
        handler._handle_post = AsyncMock()

        notification = Mock()
        notification.reason = "mention"
        notification.author.handle = "spammer.bsky.social"

        original_limiter = message_handler._limiter
        original_limit = message_handler._user_limit

        # use a 1/minute limit so the second call is blocked
        test_storage = MemoryStorage()
        test_limiter = MovingWindowRateLimiter(test_storage)
        test_limit = parse_limit("1/minute")

        message_handler._limiter = test_limiter
        message_handler._user_limit = test_limit

        try:
            # first call succeeds (hits the limiter, then dispatches)
            await message_handler.MessageHandler.handle_notification(handler, notification)
            handler._handle_post.assert_called_once()

            handler._handle_post.reset_mock()

            # second call is rate limited — _handle_post not called
            await message_handler.MessageHandler.handle_notification(handler, notification)
            handler._handle_post.assert_not_called()
        finally:
            message_handler._limiter = original_limiter
            message_handler._user_limit = original_limit


class TestSSRFProtection:
    """Test that check_urls blocks private IPs."""

    def test_private_ips_detected(self):
        private_ips = ["127.0.0.1", "10.0.0.1", "192.168.1.1", "172.16.0.1", "::1"]
        for ip_str in private_ips:
            ip = ipaddress.ip_address(ip_str)
            assert ip.is_private or ip.is_loopback or ip.is_link_local, f"{ip_str} should be blocked"

    def test_public_ips_allowed(self):
        public_ips = ["8.8.8.8", "1.1.1.1", "140.82.121.4"]
        for ip_str in public_ips:
            ip = ipaddress.ip_address(ip_str)
            assert not (ip.is_private or ip.is_loopback or ip.is_link_local), f"{ip_str} should be allowed"
