"""Review comments on phi's pull requests, read from the repository's knot.

Since tangled's org.tangled migration a comment is an
`org.tangled.feed.comment` in the repository DID's own account, hosted by its
knot, stamped with the commenter as `x-tngl-editor`. Its subject is the
pull's ticket or one of its patch rounds. The knot answers listRecords
directly; this polls it. The jetstream path in core/ops_log.py shares the
handled set, so a comment wakes phi at most once.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from bot.config import settings
from bot.core.ops_log import comment_target

logger = logging.getLogger("bot.review_poll")

COMMENT_NSID = "org.tangled.feed.comment"
TICKET_NSID = "org.tangled.track.ticket"
PATCH_NSID = "org.tangled.review.patch"
BOBBIN = "https://api.tangled.org/xrpc"

HANDLED_FILE = Path("/data/review_comments_handled.json")
_HANDLED_KEEP = 200
_LOOKBACK_SECONDS = 3 * 60 * 60

_pds_cache: dict[str, str] = {}
_started_at = time.time()


def _load() -> list[str]:
    try:
        return list(json.loads(HANDLED_FILE.read_text())["handled"])
    except Exception:
        return []


def was_handled(uri: str) -> bool:
    return uri in _load()


def mark_handled(uri: str) -> None:
    handled = [u for u in _load() if u != uri] + [uri]
    try:
        HANDLED_FILE.parent.mkdir(parents=True, exist_ok=True)
        HANDLED_FILE.write_text(json.dumps({"handled": handled[-_HANDLED_KEEP:]}))
    except Exception as e:
        logger.warning(f"failed to persist handled review comments: {e}")


async def resolve_pds(did: str, http: httpx.AsyncClient) -> str | None:
    if did in _pds_cache:
        return _pds_cache[did]
    if not did.startswith("did:plc:"):
        return None
    try:
        doc = (await http.get(f"https://plc.directory/{did}", timeout=10)).json()
        for svc in doc.get("service") or []:
            if svc.get("id") == "#atproto_pds":
                _pds_cache[did] = str(svc["serviceEndpoint"])
                return _pds_cache[did]
    except Exception as e:
        logger.debug(f"pds lookup failed for {did}: {e}")
    return None


def _fresh_enough(created_at: str) -> bool:
    """Ignore comments older than the lookback at first sight — a fresh
    deploy must not wake phi for last week's reviews — and anything the
    jetstream path already handled before this module existed: its watched
    cursor is the newest comment it woke her for (2026-08-21 18:45, the
    first poll re-woke her for a comment answered at 17:42)."""
    from datetime import datetime

    from bot.core.ops_log import _watched_cursor

    try:
        ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
    except Exception:
        return True
    if ts < _started_at - _LOOKBACK_SECONDS:
        return False
    return ts * 1_000_000 > _watched_cursor()


async def _pull_by_phi(
    subject: str, phi_did: str, knot: str, http: httpx.AsyncClient
) -> str | None:
    """The ticket uri a comment subject belongs to, when that ticket is a pull
    phi opened; None for anything else."""
    did, collection, rkey = (subject.removeprefix("at://").split("/") + ["", ""])[:3]
    if collection == PATCH_NSID:
        response = await http.get(
            f"{knot}/xrpc/com.atproto.repo.getRecord",
            params={"repo": did, "collection": PATCH_NSID, "rkey": rkey},
            timeout=10,
        )
        rkey = str(((response.json().get("value") or {}).get("ticket")) or "")
    elif collection != TICKET_NSID:
        return None
    ticket = f"at://{did}/{TICKET_NSID}/{rkey}"
    if ticket not in _ticket_authors:
        view = (
            await http.get(
                f"{BOBBIN}/org.tangled.track.getTicketView",
                params={"uri": ticket},
                timeout=10,
            )
        ).json()
        is_pull = bool(view.get("targetBranch"))
        _ticket_authors[ticket] = (
            str((view.get("author") or {}).get("did") or "") if is_pull else ""
        )
    return ticket if _ticket_authors[ticket] == phi_did else None


_ticket_authors: dict[str, str] = {}


async def new_review_comments(
    phi_did: str,
    reviewer_dids: tuple[str, ...],
    http: httpx.AsyncClient,
    repo_dids: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Unhandled comments by the reviewers on phi's pull requests, oldest
    first. Each carries `pull`, the ticket uri phi reads it from."""
    found: list[dict[str, Any]] = []
    for repo in repo_dids or settings.review_repo_dids:
        knot = await resolve_pds(repo, http)
        if not knot:
            continue
        try:
            response = await http.get(
                f"{knot}/xrpc/com.atproto.repo.listRecords",
                params={
                    "repo": repo,
                    "collection": COMMENT_NSID,
                    "limit": 25,
                    "reverse": "true",
                },
                timeout=10,
            )
            records = json.loads(response.text, strict=False).get("records") or []
        except Exception as e:
            logger.debug(f"review poll: listRecords failed for {repo}: {e}")
            continue
        for r in records:
            value = r.get("value") or {}
            uri = str(r.get("uri") or "")
            commenter = str(value.get("x-tngl-editor") or "")
            if commenter not in reviewer_dids:
                continue
            if not _fresh_enough(str(value.get("createdAt") or "")):
                continue
            if was_handled(uri):
                continue
            try:
                pull = await _pull_by_phi(comment_target(value), phi_did, knot, http)
            except Exception as e:
                logger.debug(f"review poll: subject lookup failed for {uri}: {e}")
                continue
            if pull:
                found.append(
                    {"uri": uri, "did": commenter, "record": value, "pull": pull}
                )
    found.sort(key=lambda c: str(c["record"].get("createdAt") or ""))
    return found
