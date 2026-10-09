"""Read phi's daily promotion docket off her PDS.

The docket is regenerated daily by the `docket` Prefect flow (see
my-prefect-server/flows/docket.py), event-triggered after phi-atlas
completion. It lands as a blob on phi's PDS under
`io.zzstoatzz.phi.docket/self` with a small header (generatedAt,
candidateCount, atlasRecordCid, blob ref); the blob carries the full
candidates list.

The primitive is the docket. This module is the bot-side projection
used by the cockpit. Phi reads the record blob through inspect_record_media.

Cached by PDS record CID, not by clock — the docket changes only when
Prefect writes a new one (after a new atlas), so there's no point
re-fetching unchanged state. Same pattern as `bot/core/atlas.py`.
"""

import json
import logging
from typing import Any

import httpx
from atproto_client.models.utils import get_model_as_dict

from bot.core.atproto_client import bot_client

logger = logging.getLogger("bot.core.docket")

PHI_DID = "did:plc:65sucjiel52gefhcdcypynsr"
PDS_BASE = "https://bsky.social"
DOCKET_COLLECTION = "io.zzstoatzz.phi.docket"
DOCKET_RKEY = "self"

_cached_record_cid: str | None = None
_cached_docket: dict[str, Any] | None = None


async def _fetch_record() -> dict[str, Any] | None:
    """Read the small metadata record (generatedAt + candidateCount + blob ref)."""
    await bot_client.authenticate()
    try:
        result = bot_client.client.com.atproto.repo.get_record(
            {"repo": PHI_DID, "collection": DOCKET_COLLECTION, "rkey": DOCKET_RKEY}
        )
    except Exception as e:
        logger.info(f"no docket record on PDS yet: {e}")
        return None
    return {
        "uri": result.uri,
        "cid": result.cid,
        "value": get_model_as_dict(result.value),
    }


async def _fetch_blob(blob_cid: str) -> bytes:
    """Fetch the docket blob via com.atproto.sync.getBlob.

    bsky.social is the entryway; the call returns a 302 redirecting to
    the actual PDS that holds the blob. follow_redirects=True handles
    that without having to resolve phi's PDS host ourselves.
    """
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(
            f"{PDS_BASE}/xrpc/com.atproto.sync.getBlob",
            params={"did": PHI_DID, "cid": blob_cid},
        )
        resp.raise_for_status()
        return resp.content


async def get_docket() -> dict[str, Any] | None:
    """Return the parsed docket JSON, or None if no docket has been written yet.

    Cached by PDS record CID: same record → cached parse, no second fetch.
    When prefect writes a new docket the record CID changes and we re-fetch.
    """
    global _cached_record_cid, _cached_docket

    record = await _fetch_record()
    if record is None:
        return None

    record_cid = record.get("cid")
    if record_cid and record_cid == _cached_record_cid and _cached_docket is not None:
        return _cached_docket

    blob_ref = (record.get("value") or {}).get("blob") or {}
    blob_cid = ((blob_ref.get("ref") or {}).get("$link")) or blob_ref.get("cid")
    if not blob_cid:
        logger.warning(f"docket record has no blob ref: {record}")
        return None

    blob_bytes = await _fetch_blob(blob_cid)
    try:
        docket = json.loads(blob_bytes)
    except json.JSONDecodeError as e:
        logger.warning(f"docket blob {blob_cid} is not valid JSON: {e}")
        return None

    _cached_record_cid = record_cid
    _cached_docket = docket
    return docket
