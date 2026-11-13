"""An account's PDS is read from its DID document and follows a move."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core import identity

DID = "did:plc:example"


def _doc(endpoint: str):
    return SimpleNamespace(
        service=[
            SimpleNamespace(id="#bsky_notif", service_endpoint="https://other.example"),
            SimpleNamespace(id="#atproto_pds", service_endpoint=endpoint),
        ]
    )


@pytest.fixture
def resolve(monkeypatch):
    monkeypatch.setattr(identity, "_cache", {})
    resolve = AsyncMock(return_value=_doc("https://old.example/"))
    monkeypatch.setattr(identity._resolver.did, "resolve", resolve)
    return resolve


async def test_the_endpoint_is_cached_briefly_and_then_read_again(resolve, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(identity.time, "monotonic", lambda: clock[0])

    assert await identity.pds_for(DID) == "https://old.example"
    resolve.return_value = _doc("https://new.example")
    assert await identity.pds_for(DID) == "https://old.example"
    clock[0] = identity.TTL_SECONDS + 1
    assert await identity.pds_for(DID) == "https://new.example"


async def test_a_failed_lookup_keeps_the_last_answer(resolve, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(identity.time, "monotonic", lambda: clock[0])
    await identity.pds_for(DID)
    clock[0] = identity.TTL_SECONDS + 1
    resolve.side_effect = RuntimeError("plc is down")

    assert await identity.pds_for(DID) == "https://old.example"


async def test_an_account_with_no_pds_raises(resolve):
    resolve.return_value = None
    with pytest.raises(ValueError, match=DID):
        await identity.pds_for(DID)
