"""Mentionable handles — people who have opted in to being @tagged by phi.

Stored as a singleton record on phi's PDS at:
  at://{did}/io.zzstoatzz.phi.mentionConsent/self
"""

import logging
from datetime import UTC, datetime

from bot.core.atproto_client import bot_client

logger = logging.getLogger("bot.mentionable")

COLLECTION = "io.zzstoatzz.phi.mentionConsent"
RKEY = "self"

_handles: set[str] = set()
_loaded = False


async def _load() -> None:
    global _handles, _loaded
    await bot_client.authenticate()
    assert bot_client.client.me is not None
    try:
        result = bot_client.client.com.atproto.repo.get_record(
            {"repo": bot_client.client.me.did, "collection": COLLECTION, "rkey": RKEY}
        )
        _handles = set(result.value.get("handles", []))
        logger.info(f"loaded {len(_handles)} mentionable handles from PDS")
    except Exception:
        _handles = set()
        logger.info("no mentionable handles record on PDS yet")
    _loaded = True


async def _save() -> None:
    await bot_client.authenticate()
    assert bot_client.client.me is not None
    bot_client.client.com.atproto.repo.put_record(
        data={
            "repo": bot_client.client.me.did,
            "collection": COLLECTION,
            "rkey": RKEY,
            "record": {
                "$type": COLLECTION,
                "handles": sorted(_handles),
                "updatedAt": datetime.now(UTC).isoformat(),
            },
        }
    )


async def get_mentionable_handles() -> set[str]:
    if not _loaded:
        await _load()
    return set(_handles)


async def add_handle(handle: str) -> set[str]:
    if not _loaded:
        await _load()
    _handles.add(handle)
    await _save()
    logger.info(f"added {handle} to mentionable handles")
    return set(_handles)


async def remove_handle(handle: str) -> set[str]:
    if not _loaded:
        await _load()
    _handles.discard(handle)
    await _save()
    logger.info(f"removed {handle} from mentionable handles")
    return set(_handles)
