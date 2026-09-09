"""Read Bluesky post URLs as versioned records with bounded visual evidence."""

import json
import re

import httpx
from atproto import AtUri
from pydantic_ai import BinaryContent

from bot.core.media import fetch_blob_bytes, fetch_record, find_allowed_blobs

MAX_IMAGES = 6
MAX_IMAGE_BYTES = 2_000_000


def post_uri_from_url(url: str) -> str | None:
    parsed = httpx.URL(url)
    if parsed.scheme not in {"http", "https"} or parsed.host != "bsky.app":
        return None
    match = re.fullmatch(r"/profile/([^/]+)/post/([a-zA-Z0-9_~-]+)/?", parsed.path)
    if not match:
        return None
    actor, rkey = match.groups()
    return f"at://{actor}/app.bsky.feed.post/{rkey}"


async def read_post_url(url: str, uri: str) -> list[str | BinaryContent]:
    """Read the post and exact cited parent/root versions, never crawl replies."""
    post = await fetch_record(uri)
    if not post.get("cid") or not post.get("uri"):
        raise ValueError("post read returned no versioned identity")
    context = []
    readable = [post]
    seen = {(post["uri"], post["cid"])}
    reply = post["value"].get("reply") or {}
    for role in ("parent", "root"):
        ref = reply.get(role) or {}
        key = (ref.get("uri"), ref.get("cid"))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        entry = {"role": role, "ref": ref, "status": "unavailable"}
        try:
            record = await fetch_record(ref["uri"])
            if record["uri"] == ref["uri"] and record["cid"] == ref["cid"]:
                entry.update(status="available", record=record)
                readable.append(record)
            else:
                entry["status"] = "version_changed"
        except Exception as error:
            entry["error"] = f"{type(error).__name__}: {error}"
        context.append(entry)

    media = []
    attachments: list[str | BinaryContent] = []
    attempts = 0
    for record in readable:
        did = AtUri.from_str(record["uri"]).host
        for blob in find_allowed_blobs(record["value"]):
            if not blob.is_image:
                continue
            item = {
                "record_uri": record["uri"],
                "record_cid": record["cid"],
                "blob_cid": blob.cid,
                "status": "not_loaded",
            }
            media.append(item)
            if attempts >= MAX_IMAGES or (blob.size and blob.size > MAX_IMAGE_BYTES):
                continue
            attempts += 1
            try:
                data = await fetch_blob_bytes(did, blob.cid, max_bytes=MAX_IMAGE_BYTES)
                if not data:
                    raise ValueError("empty image")
                attachments.extend(
                    [
                        f"Image from {record['uri']} (record CID {record['cid']}, blob {blob.cid}).",
                        BinaryContent(data=data, media_type=blob.mime_type),
                    ]
                )
                item["status"] = "attached"
            except Exception as error:
                item.update(
                    status="unavailable", error=f"{type(error).__name__}: {error}"
                )
    evidence = {
        "url": url,
        "source_type": "atproto_post",
        "post": post,
        "context": context,
        "images": media,
        "scope": "Requested post and available exact parent/root versions only. Replies have not been read. Linked and quoted records are references, not inspected contents.",
    }
    return [json.dumps(evidence, ensure_ascii=False), *attachments]
