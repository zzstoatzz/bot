"""Tests for the graze.social REST client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bot.core.graze_client import BASE_URL, GrazeClient


@pytest.fixture
def graze():
    return GrazeClient(handle="test.bsky.social", password="test-pass")


def _login_response():
    """Fake successful login response."""
    resp = httpx.Response(
        200,
        json={"user": {"id": 42}},
        request=httpx.Request("POST", f"{BASE_URL}/app/login"),
    )
    return resp


def _ok_response(json=None):
    resp = httpx.Response(
        200,
        json=json or {},
        request=httpx.Request("GET", BASE_URL),
    )
    return resp


class TestLogin:
    async def test_login_caches_session(self, graze):
        with patch("bot.core.graze_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = _login_response()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await graze._login()
            assert graze._user_id == 42
            assert graze._cookies is not None

    async def test_ensure_session_skips_if_cached(self, graze):
        graze._cookies = httpx.Cookies()
        graze._user_id = 42
        # should not attempt login
        with patch.object(graze, "_login") as mock_login:
            await graze._ensure_session()
            mock_login.assert_not_called()

    async def test_ensure_session_logs_in_if_no_cookies(self, graze):
        with patch.object(graze, "_login") as mock_login:
            await graze._ensure_session()
            mock_login.assert_called_once()


class TestListFeeds:
    async def test_list_feeds(self, graze):
        feeds_data = [
            {"id": 1, "display_name": "Jazz", "feed_uri": "at://did/gen/jazz"},
            {"id": 2, "display_name": "Blues", "feed_uri": "at://did/gen/blues"},
        ]

        async def fake_request(method, path, **kwargs):
            return _ok_response(json=feeds_data)

        with patch.object(graze, "_request", side_effect=fake_request):
            result = await graze.list_feeds()

        assert len(result) == 2
        assert result[0]["display_name"] == "Jazz"


class TestReloginOn401:
    async def test_request_retries_on_401(self, graze):
        graze._cookies = httpx.Cookies()
        graze._user_id = 42

        call_count = 0

        async def mock_request(method, path, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    401,
                    request=httpx.Request("GET", f"{BASE_URL}{path}"),
                )
            return httpx.Response(
                200,
                json={"ok": True},
                request=httpx.Request("GET", f"{BASE_URL}{path}"),
            )

        with (
            patch("bot.core.graze_client.httpx.AsyncClient") as mock_cls,
            patch.object(graze, "_login", new_callable=AsyncMock) as mock_login,
        ):
            mock_client = AsyncMock()
            mock_client.request = mock_request
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            r = await graze._request("GET", "/app/my_feeds")
            assert r.status_code == 200
            mock_login.assert_called_once()
