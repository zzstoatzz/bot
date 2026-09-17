"""Startup authentication must survive transient Bluesky transport failures.

Regression for the 2026-09-15 outage: a single InvokeTimeoutError during
client.login() exited the app, fly exhausted its restart budget in about
two minutes, and phi stayed down for sixteen hours.
"""

import pytest
from atproto_client import exceptions as atproto_exceptions

from bot.core import atproto_client as mod


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    return recorded


@pytest.fixture
def client(monkeypatch, sleeps):
    monkeypatch.setattr(mod, "_get_session_string", lambda: None)
    return mod.BotClient()


async def test_login_retries_transient_timeouts(client, sleeps):
    calls = 0

    def flaky_login(**kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise atproto_exceptions.InvokeTimeoutError()

    client.client.login = flaky_login

    await client.authenticate()

    assert client._authenticated
    assert calls == 3
    assert sleeps == [2.0, 4.0]


async def test_login_gives_up_after_max_attempts(client, sleeps):
    calls = 0

    def always_timeout(**kwargs):
        nonlocal calls
        calls += 1
        raise atproto_exceptions.InvokeTimeoutError()

    client.client.login = always_timeout

    with pytest.raises(atproto_exceptions.InvokeTimeoutError):
        await client.authenticate()

    assert calls == mod.LOGIN_ATTEMPTS
    assert len(sleeps) == mod.LOGIN_ATTEMPTS - 1
    assert not client._authenticated


async def test_bad_credentials_do_not_retry(client, sleeps):
    calls = 0

    def unauthorized(**kwargs):
        nonlocal calls
        calls += 1
        raise atproto_exceptions.UnauthorizedError(None)

    client.client.login = unauthorized

    with pytest.raises(atproto_exceptions.UnauthorizedError):
        await client.authenticate()

    assert calls == 1
    assert sleeps == []


async def test_network_error_during_session_restore_keeps_session_file(
    client, monkeypatch, tmp_path
):
    session_file = tmp_path / ".session"
    session_file.write_text("saved-session")
    monkeypatch.setattr(mod, "SESSION_FILE", session_file)
    monkeypatch.setattr(mod, "_get_session_string", lambda: "saved-session")

    seen: list[dict] = []

    def always_timeout(**kwargs):
        seen.append(kwargs)
        raise atproto_exceptions.InvokeTimeoutError()

    client.client.login = always_timeout

    with pytest.raises(atproto_exceptions.InvokeTimeoutError):
        await client.authenticate()

    assert all(k == {"session_string": "saved-session"} for k in seen)
    assert session_file.exists()
