"""Recent history is cross-person evidence with explicit coverage and failures."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from turbopuffer import Turbopuffer

from bot.memory.encounters import (
    indexed_time,
    read_recent_encounters,
    render_recent_encounters,
)

NOW = datetime(2026, 9, 5, 5, 0, tzinfo=UTC)


def test_index_times_sort_chronologically_across_offsets_and_precision():
    same_instant = [
        "2026-09-05T05:00:00Z",
        "2026-09-05T00:00:00-05:00",
        "2026-09-05T05:00:00.000000+00:00",
    ]
    assert len({indexed_time(value) for value in same_instant}) == 1
    assert indexed_time(same_instant[0]) < indexed_time("2026-09-05T05:00:00.1Z")
    with pytest.raises(ValueError, match="timezone"):
        indexed_time("2026-09-05T05:00:00")


def row(actor, minutes=0):
    uri = f"at://did:plc:{actor}/app.bsky.feed.post/one"
    return {
        "id": actor,
        "actor_did": f"did:plc:{actor}",
        "actor_handle": f"{actor}.test",
        "reason": "reply",
        "captured_at": (NOW - timedelta(minutes=minutes)).isoformat(),
        "indexed_at": (NOW - timedelta(minutes=minutes)).isoformat(
            timespec="microseconds"
        ),
        "source_created_at": "2026-07-22T00:00:00Z",
        "content": "an old source newly delivered",
        "source_uris": [uri],
    }


async def test_global_recent_view_names_people_dates_evidence_and_truncation():
    def serve(request):
        body = json.loads(request.content)
        assert body["rank_by"] == ["indexed_at", "desc"]
        assert body["top_k"] == 3  # Two displayed, one to establish more exist.
        assert body["filters"] == [
            "And",
            [
                [
                    "indexed_at",
                    "Gte",
                    (NOW - timedelta(days=2)).isoformat(timespec="microseconds"),
                ],
                ["indexed_at", "Lte", NOW.isoformat(timespec="microseconds")],
            ],
        ]
        return httpx.Response(
            200, json={"rows": [row("alice"), row("bob", 1), row("carol", 2)]}
        )

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        result = await read_recent_encounters(
            client, "test-encounters", since=NOW - timedelta(days=2), until=NOW, limit=2
        )
    text = render_recent_encounters(result)
    assert "@alice.test" in text and "@bob.test" in text
    assert "carol" not in text
    assert "more records in this window" in text
    assert "source created 2026-07-22" in text
    assert "captured 2026-09-05" in text
    assert row("alice")["source_uris"][0] in text
    assert "responses and decisions are not represented" in text


async def test_recovery_capture_does_not_displace_recently_indexed_encounters():
    recent = row("alice", 1)
    recovered = row("bob", 60 * 24 * 7)
    recovered["captured_at"] = NOW.isoformat()

    def serve(request):
        body = json.loads(request.content)
        # Apply the wire query to adversarial data: capture order and event
        # order disagree. This exercises filtering as well as the top-k choice.
        _, filters = body["filters"]
        lower_field, _, lower = filters[0]
        upper_field, _, upper = filters[1]
        rows = [
            event
            for event in [recovered, recent]
            if event[lower_field] >= lower and event[upper_field] <= upper
        ]
        field, direction = body["rank_by"]
        rows.sort(key=lambda event: event[field], reverse=direction == "desc")
        return httpx.Response(200, json={"rows": rows[: body["top_k"]]})

    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        for window in [timedelta(days=2), timedelta(days=10)]:
            result = await read_recent_encounters(
                client, "test-encounters", since=NOW - window, until=NOW, limit=1
            )
            assert [event["id"] for event in result["rows"]] == ["alice"]
            assert result["has_more"] == (window == timedelta(days=10))


@pytest.mark.parametrize(
    "status,expected", [(200, "ok"), (404, "not_initialized"), (503, "unavailable")]
)
async def test_empty_missing_and_failed_history_are_distinct(status, expected):
    with Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    status,
                    json={"rows": []} if status == 200 else {"error": "unavailable"},
                )
            )
        ),
    ) as client:
        result = await read_recent_encounters(
            client, "test-encounters", since=NOW - timedelta(days=2), until=NOW
        )
    assert result["status"] == expected
    rendered = render_recent_encounters(result)
    assert ("No captured encounters in this window" in rendered) == (status == 200)
    if status == 404:
        assert "Older memory may exist elsewhere" in rendered
    if status == 503:
        assert "read failed" in rendered
