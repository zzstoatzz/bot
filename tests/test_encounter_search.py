"""The transport contract preserves coverage and original event references."""

import json

import httpx
import pytest
from turbopuffer import Turbopuffer

from bot.memory.encounter_search import read_encounter, search_encounters


def client(serve):
    return Turbopuffer(
        api_key="test",
        base_url="https://memory.test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    )


async def test_search_without_person_reads_one_namespace_and_keeps_exact_reference():
    requests = []
    source = {
        "id": "immutable-event",
        "actor_did": "did:plc:ali",
        "content": "ten vote cap",
        "event_uri": "at://did:plc:ali/app.bsky.feed.post/one",
        "event_cid": "original-version",
    }

    def serve(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["rank_by"] == ["content", "BM25", "vote cap"]
        assert body["filters"] == ["kind", "Eq", "encounter"]
        assert body["top_k"] == 2
        return httpx.Response(200, json={"rows": [source, {"id": "another"}]})

    with client(serve) as storage:
        result = await search_encounters(
            storage, "private-encounters", "vote cap", limit=1
        )
    assert len(requests) == 1
    assert result["status"] == "ok" and result["has_more"]
    assert result["rows"][0]["event_cid"] == source["event_cid"]
    assert result["rows"][0]["id"] == source["id"]


async def test_exact_read_returns_original_body_without_reconstructing_it():
    original = json.dumps(
        {"text": "a later followup", "reply": {"parent": {"uri": "at://original"}}}
    )

    def serve(request):
        assert json.loads(request.content)["filters"] == [
            "And",
            [["kind", "Eq", "encounter"], ["id", "Eq", "source-id"]],
        ]
        return httpx.Response(
            200, json={"rows": [{"id": "source-id", "record_json": original}]}
        )

    with client(serve) as storage:
        result = await read_encounter(storage, "private-encounters", "source-id")
    assert result["rows"][0]["record_json"] == original


@pytest.mark.parametrize(
    ("status", "expected"),
    [(404, "not_initialized"), (503, "unavailable"), (200, "ok")],
)
async def test_absent_index_failure_and_empty_result_are_distinct(status, expected):
    with client(lambda request: httpx.Response(status, json={"rows": []})) as storage:
        result = await search_encounters(storage, "private-encounters", "ali")
    assert result["status"] == expected
    assert result["rows"] == []
