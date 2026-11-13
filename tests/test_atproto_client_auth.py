"""Startup authentication must survive transient Bluesky transport failures.

Regression for the 2026-09-15 outage: a single InvokeTimeoutError during
client.login() exited the app, fly exhausted its restart budget in about
two minutes, and phi stayed down for sixteen hours.
"""

from unittest.mock import AsyncMock

import pytest
from atproto import Session
from atproto_client import exceptions as atproto_exceptions

from bot.core import atproto_client as mod
from bot.core import identity

PDS = "https://pds.example"


@pytest.fixture(autouse=True)
def resolved_pds(monkeypatch):
    lookup = AsyncMock(return_value=PDS)
    monkeypatch.setattr(identity, "pds_for_handle", lookup)
    return lookup


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


def _saved(pds: str) -> str:
    return Session("phi.test", "did:plc:phi", "access", "refresh", pds).encode()


async def test_a_session_from_another_host_is_discarded(client, monkeypatch, tmp_path):
    """After an account move the old host still accepts its own session."""
    session_file = tmp_path / ".session"
    session_file.write_text(_saved("https://old.example"))
    monkeypatch.setattr(mod, "SESSION_FILE", session_file)
    monkeypatch.setattr(mod, "_get_session_string", session_file.read_text)
    seen: list[dict] = []
    client.client.login = lambda **kwargs: seen.append(kwargs)

    await client.authenticate()

    assert [set(k) for k in seen] == [{"login", "password"}]
    assert client.client._base_url == f"{PDS}/xrpc"
    assert not session_file.exists()


async def test_a_session_from_her_pds_is_reused(client, monkeypatch):
    saved = _saved(PDS + "/")
    monkeypatch.setattr(mod, "_get_session_string", lambda: saved)
    seen: list[dict] = []
    client.client.login = lambda **kwargs: seen.append(kwargs)

    await client.authenticate()

    assert seen == [{"session_string": saved}]


async def test_a_failed_lookup_trusts_the_saved_session(
    client, monkeypatch, resolved_pds
):
    saved = _saved("https://old.example")
    monkeypatch.setattr(mod, "_get_session_string", lambda: saved)
    resolved_pds.side_effect = ValueError("plc is down")
    seen: list[dict] = []
    client.client.login = lambda **kwargs: seen.append(kwargs)

    await client.authenticate()

    assert seen == [{"session_string": saved}]


async def test_a_failed_lookup_without_a_session_stops_startup(client, resolved_pds):
    resolved_pds.side_effect = ValueError("plc is down")

    with pytest.raises(ValueError, match="plc is down"):
        await client.authenticate()
