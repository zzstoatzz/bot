"""Resolve the operator's profile from settings.owner_handle.

owner_handle in settings is a Handle | Did. The atproto SDK's
`app.bsky.actor.get_profile(actor=...)` accepts either and returns the
full profile (handle, did, display_name, description, etc).

Cached at 1h — display names rarely change and this is read every prompt
build during scheduled passes.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from bot.config import settings
from bot.core.atproto_client import bot_client

logger = logging.getLogger("bot.operator")

_TTL_SECONDS = 3600  # 1h
_cache: dict[str, Any] = {"profile": None, "fetched_at": 0.0}


async def get_operator_profile() -> dict[str, str] | None:
    """Resolve the configured owner identifier to a profile.

    Returns a dict with handle, did, display_name (and description if set).
    Returns None if resolution fails — callers should degrade gracefully.
    """
    now = time.time()
    if _cache["profile"] and now - _cache["fetched_at"] < _TTL_SECONDS:
        return _cache["profile"]

    try:
        await bot_client.authenticate()
        profile = bot_client.client.app.bsky.actor.get_profile(
            params={"actor": settings.owner_handle}
        )
    except Exception as e:
        logger.debug(f"operator profile resolution failed: {e}")
        return None

    resolved = {
        "handle": profile.handle,
        "did": profile.did,
        "display_name": (profile.display_name or "").strip() or profile.handle,
        "description": (profile.description or "").strip(),
    }
    _cache["profile"] = resolved
    _cache["fetched_at"] = now
    return resolved
