"""Atlas detail must recover the referenced row, not reconstruct a clipped label."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from bot.memory.atlas_source import read_atlas_source
from bot.tools import atlas as atlas_tools


async def inspect_with_row(row, *, failure=None):
    query = Mock(return_value=SimpleNamespace(rows=[] if row is None else [row]))
    query.side_effect = failure
    client = Mock()
    client.namespace.return_value.query = query
    point = {
        "id": "interaction-ali-exchange",
        "kind": "interaction",
        "label": "user: clipped beginning",
        "refs": {"tpuf_namespace": "phi-users-ali_example", "tpuf_id": "original"},
    }
    captured = {}

    def register(fn):
        captured[fn.__name__] = fn
        return fn

    atlas_tools.register(SimpleNamespace(tool=register))
    ctx = SimpleNamespace(deps=SimpleNamespace(memory=SimpleNamespace(client=client)))
    with patch.object(
        atlas_tools, "get_atlas", AsyncMock(return_value={"points": [point]})
    ):
        output = await captured["inspect_atlas"](ctx, point_id=point["id"])
    return output, query


async def test_point_inspection_reads_full_exact_source_with_dates_and_evidence():
    row = SimpleNamespace(
        id="original",
        kind="interaction",
        content="user: original question\nbot: " + "complete answer " * 30,
        created_at="2026-09-04T23:24:36.318468",
        status="active",
        source_uris=["at://did:plc:ali/app.bsky.feed.post/parent"],
    )
    output, query = await inspect_with_row(row)
    assert row.content in output
    assert row.created_at in output
    assert row.source_uris[0] in output
    assert "status: active" in output
    assert query.call_args.kwargs == {
        "rank_by": ("id", "asc"),
        "filters": ("id", "Eq", "original"),
        "top_k": 1,
        "include_attributes": True,
    }


async def test_source_status_is_preserved_and_legacy_provenance_is_not_invented():
    output, _ = await inspect_with_row(
        SimpleNamespace(
            id="original", content="dated interpretation", status="superseded"
        )
    )
    assert "status: superseded" in output
    assert "created_at: unavailable" in output
    assert "(none stored)" in output


async def test_missing_row_and_failed_read_are_distinct():
    missing, _ = await inspect_with_row(None)
    failed, _ = await inspect_with_row(None, failure=RuntimeError("temporary failure"))
    assert "not found" in missing
    assert "lookup failed" in failed
    assert "not found" not in failed


async def test_unrelated_namespace_is_not_read():
    client = Mock()
    output = await read_atlas_source(
        client, {"refs": {"tpuf_namespace": "other-project", "tpuf_id": "original"}}
    )
    assert "outside Phi's memory" in output
    client.namespace.assert_not_called()
