"""Where an account's repository lives, read from its DID document.

Nothing in the bot assumes a host for anyone's PDS, Phi's included. Accounts
move, and a hardcoded or forever-cached endpoint keeps answering for a
repository that has been deactivated.
"""

import time

from atproto import AsyncIdResolver

TTL_SECONDS = 600

_resolver = AsyncIdResolver()
_cache: dict[str, tuple[float, str]] = {}


async def pds_for(did: str) -> str:
    """The account's PDS endpoint.

    A failed lookup reuses the last answer for that DID; with none, it raises
    ValueError.
    """
    cached = _cache.get(did)
    if cached and time.monotonic() - cached[0] < TTL_SECONDS:
        return cached[1]
    try:
        doc = await _resolver.did.resolve(did)
        services = (doc.service if doc else None) or []
        endpoint = next(
            str(service.service_endpoint).rstrip("/")
            for service in services
            if service.id.endswith("#atproto_pds")
        )
    except Exception as e:
        if cached:
            return cached[1]
        raise ValueError(f"no PDS found for {did}") from e
    _cache[did] = (time.monotonic(), endpoint)
    return endpoint


async def did_for_handle(handle: str) -> str:
    did = await _resolver.handle.resolve(handle)
    if not did:
        raise ValueError(f"handle {handle} does not resolve to a DID")
    return did


async def pds_for_handle(handle: str) -> str:
    return await pds_for(await did_for_handle(handle))
