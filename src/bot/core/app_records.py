"""Govern public records in atproto apps shaped like Bluesky.

An app forked from Bluesky keeps its record shapes under its own namespace:
`town.delve.feed.post` is a post, `town.delve.feed.like` a like. Those writes
go through pdsx as ordinary records, so the guard keys on the shape (the last
two NSID segments) and gives each the check its `app.bsky` twin gets.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.media import fetch_record
from bot.core.policy import ContactTarget

logger = logging.getLogger("bot.app_records")

# shape -> the tool whose declared risk the judge weighs the write against
GOVERNED_SHAPES = {
    "feed.post": "post",
    "feed.like": "like",
    "feed.repost": "repost",
    "actor.profile": "write_bio",
}


def governed_shape(collection: str) -> str | None:
    """`town.delve.feed.post` -> `feed.post`; None for app.bsky and other shapes."""
    if collection.startswith("app.bsky."):
        return None
    shape = ".".join(collection.split(".")[-2:])
    return shape if shape in GOVERNED_SHAPES else None


def _mentioned_dids(record: dict[str, Any]) -> set[str]:
    return {
        str(feature.get("did", ""))
        for facet in record.get("facets") or []
        if isinstance(facet, dict)
        for feature in facet.get("features") or []
        if isinstance(feature, dict)
        and str(feature.get("$type", "")).endswith("#mention")
    }


def _contact(uri: str, own_did: str) -> ContactTarget:
    did = uri.removeprefix("at://").split("/", 1)[0]
    if did == own_did:
        evidence = "Phi's own post."
    elif did in settings.operator_dids:
        evidence = "Configured operator's post."
    else:
        evidence = ""
    return {"uri": uri, "evidence": evidence}


async def govern_app_record(
    ctx: Any, collection: str, shape: str, tool_args: dict[str, Any]
) -> tuple[str | None, str, dict[str, Any]]:
    """Judge one write. Returns (refusal, warn_note, tool_args to send)."""
    from bot.tools.posting import _policy_gate

    app = collection.removesuffix(f".{shape}") or "another app"
    key = "record" if "record" in tool_args else "updates"
    raw = tool_args.get(key)
    record = dict(raw) if isinstance(raw, dict) else {}
    own_did = getattr(getattr(bot_client.client, "me", None), "did", "") or ""
    deps = getattr(ctx, "deps", None)
    unprompted = not getattr(deps, "notifications_context", None) and not getattr(
        deps, "author_handle", ""
    )
    when = (
        "a scheduled cycle (nobody prompted this)."
        if unprompted
        else "notification handling."
    )
    tool = GOVERNED_SHAPES[shape]

    if shape == "actor.profile":
        text = "\n".join(
            str(record[k]) for k in ("displayName", "description") if record.get(k)
        )
        if not text:
            return None, "", tool_args
        refusal, warn = await _policy_gate(
            text,
            f"Phi proposes public profile text on {app}.",
            unprompted=True,
            tool=tool,
        )
        return refusal, warn, tool_args

    if shape == "feed.post":
        strangers = _mentioned_dids(record) - set(settings.operator_dids) - {own_did}
        if strangers:
            return (
                f"refused: mention consent is not set up for {app}, so a post "
                "there cannot tag anyone but the operator. Write the post "
                "without the mention facet.",
                "",
                tool_args,
            )
        reply = record.get("reply")
        parent = reply.get("parent") if isinstance(reply, dict) else None
        parent_uri = str(parent.get("uri", "")) if isinstance(parent, dict) else ""
        text = str(record.get("text") or "") or json.dumps(record, ensure_ascii=False)
        refusal, warn = await _policy_gate(
            text,
            f"{'reply' if parent_uri else 'top-level post'} on {app}, an atproto "
            f"app outside Bluesky, written as a raw record during {when}",
            unprompted=unprompted,
            tool=tool,
            publication_text=text,
            contacts=[_contact(parent_uri, own_did)] if parent_uri else None,
        )
        return refusal, warn, tool_args

    raw_subject = record.get("subject")
    subject = raw_subject if isinstance(raw_subject, dict) else {}
    uri = str(subject.get("uri", ""))
    if not uri:
        return (
            f"refused: a {tool} record needs record.subject.uri (the AT-URI of "
            "the post); the guard fills in the cid.",
            "",
            tool_args,
        )
    if own_did and uri.startswith(f"at://{own_did}/"):
        return (
            f"refused: that's your own post; a {tool} is for other people's work",
            "",
            tool_args,
        )
    try:
        target = await fetch_record(uri, timeout=10)
    except Exception as e:
        logger.info(f"verify failed for {uri}: {e}")
        return f"refused: could not verify {uri} is a fetchable record", "", tool_args
    cid = str(target.get("cid") or "")
    if not cid:
        return f"refused: could not determine cid for {uri}", "", tool_args
    quoted = str((target.get("value") or {}).get("text") or "")[:120]
    refusal, warn = await _policy_gate(
        f"{tool} of {uri} on {app}" + (f': "{quoted}"' if quoted else ""),
        f"reaction record on {app}, triggered during {when}",
        unprompted=unprompted,
        tool=tool,
    )
    record["subject"] = {"uri": uri, "cid": subject.get("cid") or cid}
    record.setdefault("createdAt", datetime.now(UTC).isoformat())
    return refusal, warn, {**tool_args, key: record}
