"""Exact-parent reply discovery through Constellation, hydrated by AppView."""

import asyncio
import json
import logging

import httpx

from bot.core.atproto_client import BotClient

logger = logging.getLogger("bot.reply_coverage")
CONSTELLATION = "https://constellation.microcosm.blue"
APPVIEW = "https://public.api.bsky.app"


async def read_replies(http: httpx.AsyncClient, parent_uri: str, did: str) -> dict:
    uris: set[str] = set()
    cursors: set[str] = set()
    params = {
        "subject": parent_uri,
        "source": "app.bsky.feed.post:reply.parent.uri",
        "did": did,
        "limit": "100",
    }
    complete = False
    for _ in range(3):
        response = await http.get(
            f"{CONSTELLATION}/xrpc/blue.microcosm.links.getBacklinks", params=params
        )
        response.raise_for_status()
        page = response.json()
        for record in page["records"]:
            if record["did"] != did or record["collection"] != "app.bsky.feed.post":
                raise ValueError("unexpected backlink identity")
            uris.add(f"at://{did}/app.bsky.feed.post/{record['rkey']}")
        cursor = page.get("cursor")
        if not cursor:
            complete = True
            break
        if cursor in cursors:
            break
        cursors.add(cursor)
        params["cursor"] = cursor
    replies = []
    ordered = sorted(uris)
    for start in range(0, len(ordered), 25):
        response = await http.get(
            f"{APPVIEW}/xrpc/app.bsky.feed.getPosts",
            params=[("uris", uri) for uri in ordered[start : start + 25]],
        )
        response.raise_for_status()
        for post in response.json()["posts"]:
            record = post["record"]
            if (
                post["uri"] not in uris
                or post["author"]["did"] != did
                or record.get("reply", {}).get("parent", {}).get("uri") != parent_uri
            ):
                raise ValueError("unexpected hydrated reply")
            replies.append(
                {
                    "uri": post["uri"],
                    "text": record["text"],
                    "created_at": record["createdAt"],
                }
            )
    return {
        "replies": replies,
        "indexed_reply_uris": ordered,
        "index_pages_exhausted": complete,
        "unhydrated": sorted(uris - {reply["uri"] for reply in replies}),
    }


async def reply_coverage(client: BotClient, parent_uri: str) -> str:
    try:
        me = client.client.me
        if me is None:
            raise ValueError("reply history identity unavailable")
        async with httpx.AsyncClient(
            timeout=10, headers={"User-Agent": "phi (phi.zzstoatzz.io)"}
        ) as http:
            history = await read_replies(http, parent_uri, me.did)
        return (
            "[PRIOR COVERAGE — Phi's published direct replies to this exact parent, "
            "discovered through Constellation and hydrated from AppView. Index lag, "
            "missing records, and bounded pagination prevent proof of non-interaction. "
            "An old request is not new work merely because it appears in recent "
            "encounters. A reply proves prior contact, not successful resolution. "
            "Compare the draft with these answers; corrections, new developments "
            "and specifically requested follow-ups remain possible.]\n"
            + json.dumps(history, ensure_ascii=False)
        )
    except Exception as error:
        logger.warning("reply history unavailable: %s", type(error).__name__)
        return "[PRIOR COVERAGE] Reply history unavailable; absence of evidence is not proof this request is unanswered."


async def encounter_replies(client: BotClient, rows: list[dict]) -> dict[str, str]:
    targets = {
        row["id"]: row.get("event_uri") or next(iter(row.get("source_uris", [])), "")
        for row in rows
        if row.get("reason") in {"mention", "reply", "quote"}
    }
    targets = {
        key: uri for key, uri in targets.items() if "/app.bsky.feed.post/" in uri
    }
    results = await asyncio.gather(
        *(reply_coverage(client, uri) for uri in targets.values())
    )
    return dict(zip(targets, results, strict=True))
