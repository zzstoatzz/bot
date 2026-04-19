"""Activity feed: recent posts + cosmik cards merged by time, served as JSON.

Backs the home page's activity stream. Public-API only (bsky.app +
PDS listRecords) so no auth needed; cached in-process for 60s to keep
the home page from hammering upstream on every render.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger("bot.ui.activity")

PHI_DID = "did:plc:65sucjiel52gefhcdcypynsr"
ACTIVITY_CACHE_TTL = 60  # seconds

_TID_CHARSET = "234567abcdefghijklmnopqrstuvwxyz"

_cache_data: list[dict] | None = None
_cache_expires: float = 0.0

router = APIRouter()


def _tid_to_iso(tid: str) -> str:
    """Decode an AT Protocol TID (base32-sortstring) to ISO8601."""
    try:
        n = 0
        for ch in tid:
            n = n * 32 + _TID_CHARSET.index(ch)
        # 64-bit TID: bit 63=0, bits 62..10=timestamp(us), bits 9..0=clockid
        us = (n >> 10) & ((1 << 53) - 1)
        dt = datetime.fromtimestamp(us / 1_000_000, tz=UTC)
        return dt.isoformat()
    except (ValueError, OSError):
        return ""


def _post_to_item(entry: dict) -> dict:
    post = entry.get("post", {})
    record = post.get("record", {})
    uri = post.get("uri", "")
    parts = uri.split("/")
    bsky_url = (
        f"https://bsky.app/profile/{PHI_DID}/post/{parts[-1]}"
        if len(parts) >= 5
        else None
    )
    return {
        "type": "post",
        "text": record.get("text", ""),
        "time": record.get("createdAt", ""),
        "uri": uri,
        "url": bsky_url,
    }


def _card_to_item(rec: dict) -> dict:
    value = rec.get("value", {})
    card_type = value.get("type", "NOTE")
    item_type = "url" if card_type == "URL" else "note"
    content = value.get("content", {})
    # metadata may be nested under content.metadata (semble lexicon)
    meta = content.get("metadata", {}) if isinstance(content, dict) else {}

    if item_type == "url":
        card_title = content.get("title", "") or meta.get("title", "")
        desc = content.get("description", "") or meta.get("description", "")
        # skip semble tag metadata ("discussed in context of: ...")
        if desc and desc.startswith("discussed in context of:"):
            desc = ""
        text = desc or (content.get("url", "") if not card_title else "")
    else:
        card_title = content.get("title", "") if isinstance(content, dict) else ""
        text = content.get("text", "") if isinstance(content, dict) else str(content)

    rkey = rec.get("uri", "").rsplit("/", 1)[-1]
    return {
        "type": item_type,
        "text": text,
        "title": card_title or None,
        "time": _tid_to_iso(rkey),
        "uri": rec.get("uri", ""),
        "url": content.get("url") if item_type == "url" else None,
    }


async def _fetch_items() -> list[dict]:
    items: list[dict] = []
    async with httpx.AsyncClient(timeout=10) as client:
        posts_resp, cards_resp = await asyncio.gather(
            client.get(
                "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
                params={
                    "actor": PHI_DID,
                    "filter": "posts_and_author_threads",
                    "limit": 10,
                },
            ),
            client.get(
                "https://bsky.social/xrpc/com.atproto.repo.listRecords",
                params={
                    "repo": PHI_DID,
                    "collection": "network.cosmik.card",
                    "limit": 10,
                },
            ),
            return_exceptions=True,
        )

    if isinstance(posts_resp, httpx.Response) and posts_resp.status_code == 200:
        for entry in posts_resp.json().get("feed", []):
            items.append(_post_to_item(entry))

    if isinstance(cards_resp, httpx.Response) and cards_resp.status_code == 200:
        for rec in cards_resp.json().get("records", []):
            items.append(_card_to_item(rec))

    items.sort(key=lambda x: x.get("time", ""), reverse=True)
    return items


@router.get("/api/activity")
async def activity_feed():
    """Recent posts and cosmik cards, merged by time. 60s cache."""
    global _cache_data, _cache_expires
    now = time.monotonic()
    if _cache_data is not None and now < _cache_expires:
        return JSONResponse(_cache_data)

    items = await _fetch_items()
    _cache_data = items
    _cache_expires = now + ACTIVITY_CACHE_TTL
    return JSONResponse(items)
