"""Lexicon resolution and proxied XRPC methods for atproto apps beyond Bluesky.

An atproto app publishes its lexicons as `com.atproto.lexicon.schema` records
and names the repo that holds them in a `_lexicon` DNS TXT record. Its
methods are reached through phi's own PDS, which forwards a call to the
service named in the `atproto-proxy` header and signs it as her.
"""

import asyncio
import json
import re
from typing import Any

import dns.asyncresolver
import httpx
from atproto_client.exceptions import RequestErrorBase
from atproto_client.models.dot_dict import DotDict

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.media import _resolve_pds

NSID = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*(\.[a-zA-Z][a-zA-Z0-9-]*){2,}$")


def split_nsid(reference: str) -> tuple[str, str]:
    """`town.delve.feed.post#replyRef` -> (`town.delve.feed.post`, `replyRef`)."""
    nsid, _, fragment = reference.strip().partition("#")
    if not NSID.match(nsid):
        raise ValueError(f"{nsid!r} is not an NSID")
    return nsid, fragment


def authority_domain(nsid: str) -> str:
    """`town.delve.membership.join` -> `membership.delve.town`."""
    return ".".join(reversed(nsid.split(".")[:-1]))


def service_for(nsid: str) -> str | None:
    """The service an enabled method is proxied to, or None."""
    for service, methods in settings.xrpc_methods.items():
        if nsid in methods:
            return service
    return None


def enabled_methods() -> list[str]:
    return sorted(m for methods in settings.xrpc_methods.values() for m in methods)


async def lexicon_authority(nsid: str) -> str:
    """The DID that publishes this NSID's lexicon, from `_lexicon` DNS."""
    name = f"_lexicon.{authority_domain(nsid)}"
    try:
        answer = await dns.asyncresolver.resolve(name, "TXT")
    except Exception as e:
        raise LookupError(f"no TXT record at {name} ({type(e).__name__})") from e
    for record in answer:
        text = record.to_text().replace('" "', "").strip('"')
        if text.startswith("did="):
            return text.removeprefix("did=")
    raise LookupError(f"TXT record at {name} names no did")


async def fetch_lexicon(nsid: str) -> dict[str, Any]:
    """The published lexicon document for an NSID, with where it came from."""
    did = await lexicon_authority(nsid)
    pds = await _resolve_pds(did)
    async with httpx.AsyncClient(timeout=10) as http:
        response = await http.get(
            f"{pds}/xrpc/com.atproto.repo.getRecord",
            params={
                "repo": did,
                "collection": "com.atproto.lexicon.schema",
                "rkey": nsid,
            },
        )
    if response.status_code != 200:
        raise LookupError(
            f"{did} publishes no lexicon for {nsid} (HTTP {response.status_code})"
        )
    record = response.json()
    return {"uri": record["uri"], "authority": did, "schema": record["value"]}


def _invoke(
    kind: str, nsid: str, arguments: dict[str, Any] | None, service: str
) -> dict[str, Any]:
    client = bot_client.client.clone()
    client.request.set_additional_headers({"atproto-proxy": service})
    try:
        if kind == "query":
            # the SDK accepts a DotDict here at runtime; its annotation
            # names only its own generated params models
            params = DotDict(arguments) if arguments else None
            response = client.invoke_query(nsid, params=params)  # ty: ignore[invalid-argument-type]
        elif arguments is None:
            response = client.invoke_procedure(nsid)
        else:
            # the SDK serializes only its own models, so a lexicon it has no
            # model for goes as raw JSON content
            response = client.invoke_procedure(
                nsid,
                content=json.dumps(arguments).encode(),
                headers={"Content-Type": "application/json"},
            )
    except RequestErrorBase as e:
        failed = getattr(e, "response", None)
        content = getattr(failed, "content", None)
        return {
            "ok": False,
            "status": getattr(failed, "status_code", None),
            "error": getattr(content, "error", None) or type(e).__name__,
            "message": getattr(content, "message", None) or str(content or e),
        }
    content = response.content
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    return {"ok": True, "status": response.status_code, "output": content}


async def call_method(
    nsid: str, arguments: dict[str, Any] | None, service: str
) -> dict[str, Any]:
    """Call one query or procedure as phi, proxied through her PDS to `service`.

    The published lexicon decides the HTTP shape: a query sends `arguments`
    as parameters, a procedure that defines an input sends them as its body.
    """
    main = (await fetch_lexicon(nsid))["schema"].get("defs", {}).get("main", {})
    kind = main.get("type")
    if kind not in ("query", "procedure"):
        raise LookupError(f"{nsid} is a {kind or 'definitions file'}, not a method")
    if kind == "procedure" and "input" in main and arguments is None:
        arguments = {}
    await bot_client.authenticate()
    result = await asyncio.to_thread(_invoke, kind, nsid, arguments, service)
    return {"kind": kind, **result}
