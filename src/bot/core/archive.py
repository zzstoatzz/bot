"""Bounded, read-only Jetstream v2 archive pages from stream.waow.tech.

JSS column layout follows zat.dev/stream storage/segment.zig and its
jss-format-v1.md; DAG-CBOR and zstd decoding use maintained libraries.
Archive sequence and witnessed time are not a record's publication time.
"""

import asyncio
import base64
import json
import struct
import time
from collections import deque
from typing import Any, cast

import httpx
import libipld
import zstandard

HOST = "https://stream.waow.tech"
MAX_BLOCKS = 24
MAX_BYTES = 8 * 1024 * 1024
MAX_OUTPUT = 24000
_lock = asyncio.Lock()
_requests: deque[float] = deque()


def decode_archive_block(raw: bytes) -> list[dict]:
    """Validate the columnar envelope before exposing any rows."""
    offset = 0

    def column(fmt: str, n: int) -> tuple:
        nonlocal offset
        size = struct.calcsize("<" + fmt) * n
        if offset + size > len(raw):
            raise ValueError("truncated archive column")
        result = struct.unpack_from(f"<{n}{fmt}", raw, offset)
        offset += size
        return result

    n = column("I", 1)[0]
    if n > 262144:
        raise ValueError("archive block row limit")
    seq, witnessed, indexed = column("Q", n), column("q", n), column("q", n)
    kinds = column("B", n)
    lengths = [column(fmt, n) for fmt in ("B", "H", "B", "B", "I")]
    blobs = []
    for sizes in lengths:
        values = []
        for size in sizes:
            if offset + size > len(raw):
                raise ValueError("truncated archive payload")
            values.append(raw[offset : offset + size])
            offset += size
        blobs.append(values)
    if offset != len(raw):
        raise ValueError("trailing archive bytes")
    rows = []
    for i in range(n):
        rows.append(
            dict(
                seq=seq[i],
                witnessed_us=witnessed[i],
                indexed_us=indexed[i],
                kind=kinds[i],
                collection=blobs[0][i].decode(),
                did=blobs[1][i].decode(),
                rkey=blobs[2][i].decode(),
                rev=blobs[3][i].decode(),
                payload=blobs[4][i],
            )
        )
    if any(a["seq"] >= b["seq"] for a, b in zip(rows, rows[1:])):
        raise ValueError("unordered archive block")
    return rows


def _json_bytes(value):
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode()}
    raise TypeError("unsupported record value")


async def archive_page(
    key: str,
    did: str,
    collection: str,
    after_seq: int = 0,
    through_seq: int | None = None,
    contains: str = "",
    limit: int = 10,
    *,
    transport=None,
) -> dict:
    """One plan page, at most 24 blocks, 8 MiB compressed, 24k output."""
    result = cast(
        dict[str, Any],
        dict(
            source=HOST,
            did=did,
            collection=collection,
            after_seq=after_seq,
            through_seq=through_seq,
            next_after_seq=after_seq,
            complete=False,
            records=[],
            blocks_read=0,
            bytes_read=0,
        ),
    )
    headers = {"Authorization": f"Bearer {key}"}

    async def fetch(client, method, endpoint, **kwargs):
        async with client.stream(
            method,
            HOST + "/xrpc/network.bsky.jetstream." + endpoint,
            headers=headers,
            **kwargs,
        ) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                result["bytes_read"] += len(chunk)
                if result["bytes_read"] > MAX_BYTES:
                    raise ValueError("archive byte budget reached")
                body.extend(chunk)
            return bytes(body), response.status_code

    try:
        async with (
            asyncio.timeout(45),
            httpx.AsyncClient(timeout=15, transport=transport) as client,
        ):
            request = dict(
                dids=[did],
                collections=[collection],
                kinds=["commit"],
                afterSeq=after_seq,
            )
            if through_seq is not None:
                request["beforeSeq"] = through_seq
            body, _ = await fetch(client, "POST", "planSnapshot", json=request)
            plan = json.loads(body)
            tip = int(plan["sealedTipSeq"])
            end = min(through_seq, tip) if through_seq is not None else tip
            result["through_seq"] = end
            planned = min(int(plan["plannedThroughSeq"]), end)
            result["plan_stats"] = plan.get("stats", {})
            if planned < after_seq or (planned == after_seq and after_seq < end):
                raise ValueError("archive plan made no progress")
            output_size = 0
            for segment in plan["segments"]:
                name = segment["name"]
                if segment["mode"] == "blocks":
                    ranges = segment["blocks"]
                elif segment["mode"] == "segment":
                    # A whole-segment plan still supports individual getBlock reads.
                    async with client.stream(
                        "GET",
                        HOST + "/xrpc/network.bsky.jetstream.getSegment",
                        params={"name": name},
                        headers={**headers, "Range": "bytes=0-255"},
                    ) as response:
                        if response.status_code != 206:
                            raise ValueError(
                                "archive server did not honor header range"
                            )
                        header = await response.aread()
                    result["bytes_read"] += len(header)
                    if (
                        len(header) != 256
                        or header[:4] != b"jss0"
                        or struct.unpack_from("<H", header, 12)[0] != 1
                    ):
                        raise ValueError("invalid archive header")
                    count = struct.unpack_from("<I", header, 14)[0]
                    if count > 1048576:
                        raise ValueError("archive block count limit")
                    ranges = [{"first": 0, "last": count - 1}] if count else []
                else:
                    raise ValueError("unknown archive plan mode")
                for block_range in ranges:
                    for block_index in range(
                        block_range["first"], block_range["last"] + 1
                    ):
                        if result["blocks_read"] >= MAX_BLOCKS:
                            result["stop_reason"] = (
                                "block budget; continue with next_after_seq"
                            )
                            return result
                        body, _ = await fetch(
                            client,
                            "GET",
                            "getBlock",
                            params={"segment": name, "blockIndex": block_index},
                        )
                        # Streaming decompression caps even frames with a declared huge size.
                        with zstandard.ZstdDecompressor().stream_reader(body) as reader:
                            raw = reader.read(16 * 1024 * 1024 + 1)
                        if len(raw) > 16 * 1024 * 1024:
                            raise ValueError("archive decompression limit")
                        rows = decode_archive_block(raw)
                        result["blocks_read"] += 1
                        for row in rows:
                            seq = row["seq"]
                            if seq <= after_seq or seq > end:
                                continue
                            if (
                                row["did"] == did
                                and row["collection"] == collection
                                and row["kind"] in (1, 2, 3, 7)
                            ):
                                payload = row.pop("payload")
                                record = (
                                    libipld.decode_dag_cbor(payload)
                                    if payload
                                    else None
                                )
                                encoded = json.dumps(
                                    record, default=_json_bytes, ensure_ascii=False
                                )
                                if (
                                    not contains
                                    or contains.casefold() in encoded.casefold()
                                ):
                                    row["uri"] = (
                                        f"at://{did}/{collection}/{row['rkey']}"
                                    )
                                    row["operation"] = {
                                        1: "create",
                                        2: "update",
                                        3: "delete",
                                        7: "create_resync",
                                    }[row["kind"]]
                                    if len(encoded) > MAX_OUTPUT:
                                        row["record_omitted"] = (
                                            "record exceeds output budget; fetch URI from PDS if still present"
                                        )
                                    else:
                                        row["record"] = json.loads(encoded)
                                    size = len(json.dumps(row, ensure_ascii=False))
                                    if (
                                        result["records"]
                                        and output_size + size > MAX_OUTPUT
                                    ):
                                        result["stop_reason"] = (
                                            "output budget; continue with next_after_seq"
                                        )
                                        return result
                                    output_size += size
                                    result["records"].append(row)
                            result["next_after_seq"] = max(
                                result["next_after_seq"], seq
                            )
                            if len(result["records"]) >= limit:
                                result["stop_reason"] = (
                                    "record limit; continue with next_after_seq"
                                )
                                return result
            result["next_after_seq"] = max(result["next_after_seq"], planned)
            result["complete"] = planned >= end
            result["stop_reason"] = (
                "sealed snapshot exhausted"
                if result["complete"]
                else "plan page; continue with next_after_seq"
            )
    except httpx.HTTPStatusError as exc:
        result["error"] = (
            f"archive HTTP {exc.response.status_code}; no failed range skipped"
        )
        if exc.response.status_code == 429:
            result["retry_after"] = exc.response.headers.get(
                "Retry-After", "wait before retrying"
            )
    except Exception as exc:
        # Never include request headers or upstream bodies in model-visible errors.
        result["error"] = (
            f"archive read failed ({type(exc).__name__}); no failed range skipped"
        )
    return result


async def read_archive_page(key: str, did: str, collection: str, **kwargs) -> dict:
    """Fail fast under contention; don't queue background archive scans."""
    now = time.monotonic()
    while _requests and now - _requests[0] >= 60:
        _requests.popleft()
    if _lock.locked() or len(_requests) >= 6:
        return {
            "complete": False,
            "error": "archive reader busy or rate limited; retry after 60 seconds",
        }
    async with _lock:
        _requests.append(now)
        return await archive_page(key, did, collection, **kwargs)
