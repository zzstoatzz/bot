"""Archive boundaries: original records, partial reads, and resumable failures."""

import json
import struct
import time
from collections import deque

import httpx
import libipld
import pytest
import zstandard

from bot.core import archive

DID = "did:plc:test"
COL = "app.bsky.feed.post"


def block(rows):
    # Independent JSS fixture per upstream column layout.
    n = len(rows)
    payloads = [
        libipld.encode_dag_cbor({"text": text, "createdAt": "2026-04-01T00:00:00Z"})
        for _, _, text in rows
    ]
    blobs = [
        [COL.encode()] * n,
        [did.encode() for _, did, _ in rows],
        [f"r{seq}".encode() for seq, _, _ in rows],
        [b"rev"] * n,
        payloads,
    ]
    raw = struct.pack("<I", n)
    for fmt, values in [
        ("Q", [r[0] for r in rows]),
        ("q", [100] * n),
        ("q", [200] * n),
        ("B", [1] * n),
    ]:
        raw += struct.pack(f"<{n}{fmt}", *values)
    for fmt, values in zip(("B", "H", "B", "B", "I"), blobs):
        raw += struct.pack(f"<{n}{fmt}", *(len(v) for v in values))
    return raw + b"".join(v for values in blobs for v in values)


def service(raw, fail_block=None, mode="blocks"):
    def handle(request):
        assert request.headers["Authorization"] == "Bearer hidden"
        if request.url.path.endswith("planSnapshot"):
            body = json.loads(request.content)
            assert body["dids"] == [DID]
            assert body["kinds"] == ["commit"]
            return httpx.Response(
                200,
                json={
                    "sealedTipSeq": 10,
                    "plannedThroughSeq": 10,
                    "segments": [
                        {
                            "name": "seg_test.jss",
                            "mode": mode,
                            "blocks": [{"first": 0, "last": len(raw) - 1}],
                        }
                    ],
                },
            )
        if request.url.path.endswith("getSegment"):
            h = bytearray(256)
            h[:4] = b"jss0"
            struct.pack_into("<H", h, 12, 1)
            struct.pack_into("<I", h, 14, len(raw))
            return httpx.Response(206, content=bytes(h))
        i = int(request.url.params["blockIndex"])
        if i == fail_block:
            return httpx.Response(
                429, headers={"Retry-After": "12"}, text="secret body"
            )
        return httpx.Response(
            200, content=zstandard.ZstdCompressor(write_checksum=True).compress(raw[i])
        )

    return httpx.MockTransport(handle)


async def test_pagination_keeps_later_correction_and_exact_records():
    transport = service(
        [
            block(
                [
                    (1, DID, "funding joke"),
                    (2, "did:plc:other", "unrelated"),
                    (3, DID, "correction"),
                ]
            )
        ]
    )
    first = await archive.archive_page("hidden", DID, COL, limit=1, transport=transport)
    assert first["next_after_seq"] == 1
    assert not first["complete"]
    second = await archive.archive_page(
        "hidden",
        DID,
        COL,
        after_seq=1,
        through_seq=first["through_seq"],
        transport=transport,
    )
    assert [r["record"]["text"] for r in second["records"]] == ["correction"]
    assert second["complete"]
    assert second["records"][0]["witnessed_us"] == 100
    assert second["records"][0]["record"]["createdAt"] == "2026-04-01T00:00:00Z"


async def test_error_does_not_advance_past_unread_block():
    transport = service(
        [block([(1, DID, "first")]), block([(3, DID, "correction")])], fail_block=1
    )
    result = await archive.archive_page("hidden", DID, COL, transport=transport)
    assert result["next_after_seq"] == 1
    assert not result["complete"]
    assert result["retry_after"] == "12"
    assert "secret body" not in json.dumps(result)


async def test_no_matches_under_budget_is_not_complete(monkeypatch):
    monkeypatch.setattr(archive, "MAX_BLOCKS", 1)
    transport = service([block([(1, DID, "first")]), block([(3, DID, "correction")])])
    result = await archive.archive_page(
        "hidden", DID, COL, contains="correction", transport=transport
    )
    assert not result["complete"]
    assert result["records"] == []
    assert result["next_after_seq"] == 1


async def test_whole_segment_plan_reads_bounded_blocks():
    result = await archive.archive_page(
        "hidden",
        DID,
        COL,
        transport=service([block([(1, DID, "first")])], mode="segment"),
    )
    assert result["complete"]
    assert result["records"][0]["uri"] == f"at://{DID}/{COL}/r1"


@pytest.mark.parametrize(
    "raw",
    [b"", struct.pack("<I", 300000), block([(1, DID, "x")])[:-1], block([]) + b"bad"],
)
def test_malformed_blocks_are_rejected(raw):
    with pytest.raises(ValueError):
        archive.decode_archive_block(raw)


async def test_rate_limit_does_not_queue(monkeypatch):
    monkeypatch.setattr(archive, "_requests", deque([time.monotonic()] * 6))
    result = await archive.read_archive_page("hidden", DID, COL)
    assert "rate limited" in result["error"]
    assert not result["complete"]
