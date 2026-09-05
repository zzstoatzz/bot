"""Episodic memory consolidates at write time.

The reconciliation pipeline (ADD/UPDATE/DELETE/NOOP, superseded rows
patched, pedigree linked) existed only for per-user observations while
store_episodic_memory raw-appended — so once run summaries started landing
on every scheduled loop, the store was set to accumulate one permanent
near-duplicate row per run, forever. Episodic writes now flow through the
same reconciler; superseded rows are dropped from every read path.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from pydantic_ai import Agent
from turbopuffer import BadRequestError, Turbopuffer

from bot.memory.namespace_memory import NamespaceMemory
from bot.tools.memory import register


def _memory_with_episodic_ns():
    mem = NamespaceMemory.__new__(NamespaceMemory)
    ns = Mock()
    mem.namespaces = {"episodic": ns}
    mem._get_embedding = AsyncMock(return_value=[0.1] * 8)
    return mem, ns


def _decision(action, reason="r", new_content=None, new_tags=None):
    result = Mock()
    result.output.decision = SimpleNamespace(
        action=action, reason=reason, new_content=new_content, new_tags=new_tags
    )
    agent = Mock()
    agent.run = AsyncMock(return_value=result)
    return agent


def _upserted_rows(ns):
    return [
        call.kwargs["upsert_rows"][0]
        for call in ns.write.call_args_list
        if "upsert_rows" in call.kwargs
    ]


def _patched_rows(ns):
    return [
        call.kwargs["patch_rows"][0]
        for call in ns.write.call_args_list
        if call.kwargs.get("patch_rows")
    ]


SIMILAR = [
    {
        "id": "old-row",
        "content": "dug through fm.plyr.track, found three satie takes",
        "tags": ["run-summary"],
        "source_uris": ["at://old/post"],
    }
]


async def test_no_similar_is_plain_add():
    mem, ns = _memory_with_episodic_ns()
    mem._find_similar_episodic = AsyncMock(return_value=[])
    await mem.store_episodic_memory("something new", ["t"])
    rows = _upserted_rows(ns)
    assert len(rows) == 1
    assert rows[0]["content"] == "something new"
    assert rows[0]["status"] == "active"


async def test_noop_writes_nothing():
    mem, ns = _memory_with_episodic_ns()
    mem._find_similar_episodic = AsyncMock(return_value=SIMILAR)
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision("NOOP"),
    ):
        await mem.store_episodic_memory(
            "dug through fm.plyr.track, found the satie takes", ["run-summary"]
        )
    ns.write.assert_not_called()


async def test_new_citation_versions_note_without_rewriting_or_losing_old_sources():
    mem, ns = _memory_with_episodic_ns()
    existing = dict(SIMILAR[0], source_uris=["at://phi/app.bsky.feed.post/wrong"])
    mem._find_similar_episodic = AsyncMock(return_value=[existing])
    corrected = "at://devlog/app.bsky.feed.post/correction"
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision("NOOP"),
    ):
        await mem.store_episodic_memory(
            existing["content"], ["correction"], source_uris=[corrected, corrected]
        )
        sources = [*existing["source_uris"], corrected]
        assert _patched_rows(ns) == [{"id": existing["id"], "status": "superseded"}]
        stored = _upserted_rows(ns)[0]
        assert stored["source_uris"] == sources
        assert stored["submitted_source_uris"] == [corrected]
        assert stored["content"] == existing["content"]
        assert stored["supersedes"] == existing["id"]
        assert existing["source_uris"] != sources
        existing.update(stored)
        ns.write.reset_mock()
        await mem.store_episodic_memory(
            existing["content"], ["correction"], source_uris=[corrected]
        )
    ns.write.assert_not_called()


async def test_update_supersedes_and_merges():
    mem, ns = _memory_with_episodic_ns()
    mem._find_similar_episodic = AsyncMock(return_value=SIMILAR)
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision(
            "UPDATE",
            new_content="plyr archaeology: three satie takes, then the full catalog",
            new_tags=["run-summary", "plyr"],
        ),
    ):
        await mem.store_episodic_memory(
            "found a whole unlisted catalog in fm.plyr.track",
            ["run-summary"],
            source_uris=["at://new/post"],
        )
    assert _patched_rows(ns) == [{"id": "old-row", "status": "superseded"}]
    rows = _upserted_rows(ns)
    assert len(rows) == 1
    assert rows[0]["content"].startswith("plyr archaeology")
    assert rows[0]["supersedes"] == "old-row"
    assert rows[0]["source_uris"] == ["at://old/post", "at://new/post"]
    assert rows[0]["submitted_source_uris"] == ["at://new/post"]
    assert rows[0]["source_provenance_version"] == 1


@pytest.mark.parametrize("legacy", [False, True])
async def test_explicitly_submitting_inherited_reference_is_recorded_once(legacy):
    mem, ns = _memory_with_episodic_ns()
    old = dict(SIMILAR[0])
    if not legacy:
        old.update(source_provenance_version=1, submitted_source_uris=[])
    ns.query.return_value = SimpleNamespace(rows=[SimpleNamespace(**old)])
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision("NOOP"),
    ):
        saved = await mem.store_episodic_memory(
            old["content"], old["tags"], source_uris=old["source_uris"],
            preserve_text=True,
        )
        assert saved["action"] == "UPDATE"
        row = _upserted_rows(ns)[0]
        assert row["source_uris"] == old["source_uris"]
        assert row["submitted_source_uris"] == old["source_uris"]
        assert row["supersedes"] == old["id"]
        ns.query.return_value = SimpleNamespace(rows=[SimpleNamespace(**row)])
        ns.write.reset_mock()
        repeated = await mem.store_episodic_memory(
            old["content"], old["tags"], source_uris=old["source_uris"],
            preserve_text=True,
        )
        assert repeated["action"] == "NOOP"
        assert repeated["id"] == row["id"]
        ns.write.assert_not_called()


async def test_reconciler_outage_degrades_to_add():
    mem, ns = _memory_with_episodic_ns()
    mem._find_similar_episodic = AsyncMock(return_value=SIMILAR)
    broken = Mock()
    broken.run = AsyncMock(side_effect=RuntimeError("judge down"))
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=broken,
    ):
        await mem.store_episodic_memory("must not be lost", ["t"])
    rows = _upserted_rows(ns)
    assert len(rows) == 1
    assert rows[0]["content"] == "must not be lost"


class _Row(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(id=kwargs["content"], **kwargs)

    def __getitem__(self, k):
        if k == "$dist":
            return self.dist
        raise KeyError(k)


async def test_search_episodic_drops_superseded():
    mem, ns = _memory_with_episodic_ns()
    ns.query.return_value = SimpleNamespace(
        rows=[
            _Row(
                content="old version", tags=[], source="tool",
                created_at="", status="superseded", dist=0.2,
            ),
            _Row(
                content="current version", tags=[], source="tool",
                created_at="", status="active", dist=0.2,
            ),
            _Row(
                content="legacy row without status", tags=[], source="tool",
                created_at="", status=None, dist=0.2,
            ),
        ]
    )
    results = await mem.search_episodic("anything")
    contents = [r["content"] for r in results]
    assert "old version" not in contents
    assert "current version" in contents
    assert "legacy row without status" in contents
    # naming "status" in include_attributes 400s on namespaces that predate
    # the schema field (took episodic reads down in prod, 2026-08-12)
    assert ns.query.call_args.kwargs["include_attributes"] is True


async def test_find_similar_episodic_missing_namespace_degrades():
    mem, ns = _memory_with_episodic_ns()
    ns.query.side_effect = RuntimeError("namespace 'phi-episodic' was not found")
    mem.namespaces["episodic"] = ns
    with pytest.raises(RuntimeError):
        await mem._find_similar_episodic([0.1] * 8)
    # store_episodic_memory catches this and raw-ADDs
    ns.query.side_effect = RuntimeError("namespace 'phi-episodic' was not found")
    await mem.store_episodic_memory("first ever memory", ["t"])
    assert len(_upserted_rows(ns)) == 1


async def test_search_episodic_recency_beats_stale_similarity():
    from datetime import UTC, datetime, timedelta

    mem, ns = _memory_with_episodic_ns()
    now = datetime.now(UTC)
    ns.query.return_value = SimpleNamespace(
        rows=[
            _Row(  # April ops dump: slightly closer, four months old
                content="prefect check 2026-04-26: ingest healthy",
                tags=[], source="tool", status="active", dist=0.30,
                created_at=(now - timedelta(days=120)).isoformat(),
            ),
            _Row(  # last week's lived episode: a bit further, recent
                content="dug through fm.plyr.track, posted, blogged",
                tags=[], source="run:cycle", status="active", dist=0.40,
                created_at=(now - timedelta(days=5)).isoformat(),
            ),
        ]
    )
    results = await mem.search_episodic("anything", top_k=2)
    assert results[0]["content"].startswith("dug through"), (
        "a 4-month-old entry outranked last week's despite recency weighting"
    )


async def test_correction_tag_exempt_from_recency_decay():
    """A correction from four months ago must outrank a fresher ordinary
    note of equal similarity — having been wrong doesn't expire, and the
    whole point of the tag is that the memory outlives run notes."""
    from datetime import UTC, datetime, timedelta

    mem, ns = _memory_with_episodic_ns()
    now = datetime.now(UTC)
    ns.query.return_value = SimpleNamespace(
        rows=[
            _Row(
                content="relays A and B are synchronized (claimed, then retracted)",
                tags=["correction"], source="tool", status="active", dist=0.35,
                created_at=(now - timedelta(days=120)).isoformat(),
            ),
            _Row(
                content="checked the relay dashboards this morning",
                tags=[], source="run:cycle", status="active", dist=0.35,
                created_at=(now - timedelta(days=2)).isoformat(),
            ),
        ]
    )
    results = await mem.search_episodic("relay synchronization", top_k=2)
    assert results[0]["content"].startswith("relays A and B"), (
        "a 4-month-old correction lost to a 2-day-old note at equal "
        "similarity — corrections must not decay"
    )


@pytest.mark.parametrize("action", ["ADD", "UPDATE", "DELETE", "NOOP"])
async def test_save_returns_resulting_note_instead_of_candidate(action):
    mem, ns = _memory_with_episodic_ns()
    mem._find_similar_episodic = AsyncMock(return_value=SIMILAR)
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision(action, new_content="merged account", new_tags=["t"]),
    ):
        result = await mem.store_episodic_memory(
            "candidate account", ["t"], source_uris=["at://new/post"]
        )
    if action == "NOOP":
        expected = _upserted_rows(ns)[0]
        assert expected["content"] == SIMILAR[0]["content"]
        action = "UPDATE"
    else:
        expected = _upserted_rows(ns)[0]
    assert result == {
        "id": expected["id"], "action": action,
        "content": expected["content"], "source_uris": expected["source_uris"],
    }


async def test_save_tool_preserves_authored_scope_and_propagates_failed_write():
    mem, ns = _memory_with_episodic_ns()
    mem._find_similar_episodic = AsyncMock(return_value=SIMILAR)
    agent = Agent()
    register(agent)
    save = agent._function_toolset.tools["save_memory"].function
    ctx = SimpleNamespace(deps=SimpleNamespace(memory=mem))
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision("UPDATE", new_content="no reply exists", new_tags=["t"]),
    ):
        result = json.loads(await save(ctx, "no reply among the 48 returned records", ["t"]))
        assert result["stored_note"]["content"] == "no reply among the 48 returned records"
        assert result["stored_note"]["id"] == _upserted_rows(ns)[0]["id"]
        ns.write.side_effect = RuntimeError("storage unavailable")
        with pytest.raises(RuntimeError, match="storage unavailable"):
            await save(ctx, "another candidate", ["t"])


async def test_authored_qualification_survives_noop_classification():
    mem, ns = _memory_with_episodic_ns()
    previous = dict(SIMILAR[0], content="no reply exists")
    mem._find_similar_episodic = AsyncMock(return_value=[previous])
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision("NOOP"),
    ):
        saved = await mem.store_episodic_memory(
            "no reply among the 48 returned records", ["correction"], preserve_text=True
        )
    assert saved["content"] == "no reply among the 48 returned records"
    assert saved["action"] == "ADD"
    assert _upserted_rows(ns)[0]["supersedes"] == ""
    assert _upserted_rows(ns)[0]["submitted_source_uris"] == []
    assert _upserted_rows(ns)[0]["source_uris"] == []
    assert not _patched_rows(ns)


async def test_redundant_confirmation_keeps_detailed_correction_active():
    mem, ns = _memory_with_episodic_ns()
    previous = dict(
        SIMILAR[0],
        content="My check showed 48 of 100 fetched records. Codex performed the other check.",
    )
    confirmation = "Re-read the correction note. Nothing new to establish."
    mem._find_similar_episodic = AsyncMock(return_value=[previous])
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision("NOOP", reason="Adds no new information"),
    ):
        saved = await mem.store_episodic_memory(
            confirmation, ["correction"], preserve_text=True
        )
    assert saved["content"] == confirmation
    assert saved["action"] == "ADD"
    assert _upserted_rows(ns)[0]["supersedes"] == ""
    assert not _patched_rows(ns)


@pytest.mark.parametrize("action", ["UPDATE", "NOOP"])
async def test_replacement_embedding_failure_keeps_previous_note_active(action):
    mem, ns = _memory_with_episodic_ns()
    mem._find_similar_episodic = AsyncMock(return_value=SIMILAR)
    mem._get_embedding.side_effect = [[0.1] * 8, RuntimeError("embedding unavailable")]
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent",
        return_value=_decision(action, new_content="replacement", new_tags=["t"]),
    ):
        with pytest.raises(RuntimeError, match="embedding unavailable"):
            await mem.store_episodic_memory(
                "new account", ["t"], source_uris=["at://new/post"]
            )
    ns.write.assert_not_called()


@pytest.mark.parametrize("action", ["UPDATE", "DELETE"])
@pytest.mark.parametrize("reject", [False, True])
async def test_replacement_and_supersession_share_one_transport_write(action, reject):
    requests = []

    def serve(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["patch_rows"] == [{"id": "old-row", "status": "superseded"}]
        assert body["upsert_rows"][0]["supersedes"] == "old-row"
        assert body["upsert_rows"][0]["status"] == "active"
        return httpx.Response(400, json={"error": "rejected"}) if reject else httpx.Response(200, json={"rows_affected": 2})

    with Turbopuffer(
        api_key="test", base_url="https://memory.test", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(serve)),
    ) as client:
        mem = NamespaceMemory.__new__(NamespaceMemory)
        mem.namespaces = {"episodic": client.namespace("test-notes")}
        mem._find_similar_episodic = AsyncMock(return_value=SIMILAR)
        mem._get_embedding = AsyncMock(return_value=[0.1] * 8)
        with patch(
            "bot.memory.namespace_memory.get_reconciliation_agent",
            return_value=_decision(action, new_content="replacement", new_tags=["t"]),
        ):
            if reject:
                with pytest.raises(BadRequestError):
                    await mem.store_episodic_memory("replacement", ["t"])
            else:
                saved = await mem.store_episodic_memory("replacement", ["t"])
                assert saved["id"] == requests[0]["upsert_rows"][0]["id"]
    assert len(requests) == 1
