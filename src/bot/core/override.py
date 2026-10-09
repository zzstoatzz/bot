"""[OPERATOR OVERRIDE] — safe mode, driven by a record on the operator's PDS.

The override is an ``io.zzstoatzz.phi.override`` record (rkey ``self``) on
the OPERATOR's repo — not phi's, and not a control-plane flag on the bot.
Repo ownership is the authorization: anyone can write this record to their
own repo, but the bot only reads ``settings.owner_did``'s copy. atproto's
own security model is the allowlist.

The active record is rendered into context and checked at MCP mutation and
native publication boundaries. Private operator delivery also observes it;
there is no PDS-note escape channel. Runtime pause and voice reset are separate.
See docs/safety.md for the actual action boundaries and their coverage.

Everything is public and inspectable — no hidden state, per the
no-big-brother principle. Reads go straight to the operator's PDS
(resolved from the DID document via plc.directory); no bluesky appview.

Freshness: short TTL cache. On fetch failure the last known state holds
(a PDS blip shouldn't flap safe mode in either direction); if we've never
successfully fetched, the override is treated as inactive — the bot can't
be bricked by an operator-PDS outage, and the supervised-resume flow
verifies the override is visibly active before resuming phi anyway.
"""

import logging
import time
from typing import TypedDict

import httpx

from bot.config import settings

logger = logging.getLogger("bot.override")

COLLECTION = "io.zzstoatzz.phi.override"
_TTL_SECONDS = 60
_HTTP_TIMEOUT = 10


class Override(TypedDict):
    active: bool
    message: str


_INACTIVE: Override = {"active": False, "message": ""}

_pds_cache: str | None = None
_cache: dict = {"override": None, "fetched_at": 0.0}


async def _resolve_operator_pds() -> str | None:
    """Operator DID -> PDS endpoint via the DID document. Cached for the
    process lifetime (a PDS move is a redeploy-worthy event)."""
    global _pds_cache
    if _pds_cache:
        return _pds_cache
    did = settings.owner_did
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as http:
            if did.startswith("did:plc:"):
                r = await http.get(f"https://plc.directory/{did}")
            elif did.startswith("did:web:"):
                host = did.removeprefix("did:web:")
                r = await http.get(f"https://{host}/.well-known/did.json")
            else:
                logger.warning(f"unsupported DID method for operator: {did}")
                return None
            r.raise_for_status()
            doc = r.json()
        for svc in doc.get("service", []):
            if svc.get("type") == "AtprotoPersonalDataServer":
                _pds_cache = svc.get("serviceEndpoint")
                logger.info(f"operator pds resolved: {_pds_cache}")
                return _pds_cache
    except Exception as e:
        logger.warning(f"operator pds resolution failed for {did}: {e}")
    return None


async def get_override() -> Override:
    """Current override state, TTL-cached, last-known-good on failure."""
    now = time.monotonic()
    if _cache["override"] is not None and now - _cache["fetched_at"] < _TTL_SECONDS:
        return _cache["override"]

    pds = await _resolve_operator_pds()
    if pds is None:
        return _cache["override"] or _INACTIVE

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as http:
            r = await http.get(
                f"{pds}/xrpc/com.atproto.repo.getRecord",
                params={
                    "repo": settings.owner_did,
                    "collection": COLLECTION,
                    "rkey": "self",
                },
            )
        if r.status_code == 400 and "RecordNotFound" in r.text:
            override = _INACTIVE
        else:
            r.raise_for_status()
            value = r.json().get("value", {})
            override = Override(
                active=bool(value.get("active", False)),
                message=str(value.get("message", "")),
            )
    except Exception as e:
        logger.warning(f"override fetch failed (holding last known state): {e}")
        return _cache["override"] or _INACTIVE

    prev = _cache["override"]
    if prev is None or prev["active"] != override["active"]:
        logger.info(
            f"operator override {'ACTIVE' if override['active'] else 'inactive'}"
            + (f": {override['message'][:120]}" if override["active"] else "")
        )
    _cache["override"] = override
    _cache["fetched_at"] = now
    return override


def refusal_text(override: Override) -> str:
    """What an outward-facing tool returns instead of acting."""
    return (
        "operator override is active — this action was not performed.\n\n"
        f"the operator's message:\n{override['message']}\n\n"
        "public mutations and operator-message delivery refuse until the "
        "operator lifts the override. reads, search and private memory remain "
        "available. this refusal is not an outage; do not route around it "
        "through another tool or a PDS note."
    )


async def get_override_block() -> str:
    """[OPERATOR OVERRIDE] system prompt block; empty when inactive."""
    override = await get_override()
    if not override["active"]:
        return ""
    return (
        "[OPERATOR OVERRIDE]\n"
        "safe mode is active. the operator's message:\n"
        f"{override['message']}\n\n"
        "public mutations and operator-message delivery refuse while this "
        "holds. this is not a malfunction. reads, search, private memory and "
        "private thread mutes remain available. do not route around the "
        "override through another tool or a PDS note. the override is public "
        f"({COLLECTION} on the operator's repo); you can read it."
    )
