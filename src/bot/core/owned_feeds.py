"""[OWNED FEEDS] block — surface phi's curated graze feeds so she actually
browses them.

Phi has read_feed but never reaches for it (0 calls/week pre-promotion). The
likely cause is that the prompt never reminds her these feeds exist or what
they're for. Listing them with names + a one-line description in the prompt
gives her concrete handles to reach for.

Cached at 5min — graze isn't free and feed names rarely change.
"""

from __future__ import annotations

import logging
import time

from bot.core.graze_client import GrazeClient

logger = logging.getLogger("bot.owned_feeds")

_TTL_SECONDS = 300  # 5min
_cache: dict = {"text": "", "fetched_at": 0.0}


async def get_owned_feeds_block(graze: GrazeClient) -> str:
    """Compose [OWNED FEEDS] — names of phi's curated feeds."""
    now = time.time()
    if _cache["text"] and now - _cache["fetched_at"] < _TTL_SECONDS:
        return _cache["text"]

    try:
        feeds = await graze.list_feeds()
    except Exception as e:
        logger.debug(f"owned_feeds: list_feeds failed: {e}")
        return ""

    if not feeds:
        return ""

    lines = [
        "[OWNED FEEDS — read with read_feed(name=...). these are curated; "
        "they reflect what's worth attention on a specific topic, not "
        "ambient timeline.]"
    ]
    for f in feeds:
        display = f.get("display_name") or f.get("name") or "unnamed"
        uri = f.get("feed_uri") or f.get("uri") or ""
        rkey = f.get("record_name") or (uri.rsplit("/", 1)[-1] if uri else "")
        if not rkey:
            continue
        desc = (f.get("description") or "").strip().replace("\n", " ")
        desc_part = f" — {desc[:120]}" if desc else ""
        lines.append(f"- name={rkey}: {display}{desc_part}")

    block = "\n".join(lines)
    _cache["text"] = block
    _cache["fetched_at"] = now
    return block
