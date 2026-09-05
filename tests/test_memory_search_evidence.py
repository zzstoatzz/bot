"""A remembered exchange must let Phi open the original evidence.

The Ali exchange was stored with both post URIs, but memory search dropped
them. Exercise the real search tool and memory readers against a backend
that honors attribute projection, so a renderer-only fix cannot pass.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from turbopuffer import NotFoundError

from bot.agent import render_recent_conversations
from bot.memory.namespace_memory import NamespaceMemory
from bot.tools import memory as memory_tools
from bot.tools._helpers import PhiDeps

ALI = "alimabsoute.bsky.social"
PARENT = "at://did:plc:4ktckriaavgdp5cohnaliy4d/app.bsky.feed.post/3muq4brw6r72y"
REPLY = "at://did:plc:65sucjiel52gefhcdcypynsr/app.bsky.feed.post/3muq4d7kyqi2v"


class Row(SimpleNamespace):
    def __getitem__(self, key):
        if key == "$dist":
            return 0.1
        raise KeyError(key)


class Namespace:
    def __init__(self, records):
        self.records = records

    def query(self, *, include_attributes, **kwargs):
        rows = [
            Row(
                **{
                    key: value
                    for key, value in record.items()
                    if include_attributes is True or key in include_attributes
                }
            )
            for record in self.records
        ]
        return SimpleNamespace(rows=rows)


def tool_with_memory(*, legacy=False):
    record = {
        "id": "example-exchange",
        "content": "user: ten votes\nbot: the cap forces a choice",
        "created_at": "2026-09-04T23:24:36",
        "kind": "interaction",
        "tags": ["correction"],
        "source": "tool",
        "status": "active",
    }
    if not legacy:
        record["source_uris"] = [PARENT, REPLY]
    user_ns = Namespace([record])
    episodic_ns = Namespace([{**record, "kind": "note"}])
    memory = NamespaceMemory.__new__(NamespaceMemory)
    memory._get_embedding = AsyncMock(return_value=[0.1] * 8)
    memory.get_user_namespace = lambda handle: (
        user_ns if handle == ALI else Namespace([])
    )
    memory.namespaces = {"episodic": episodic_ns}
    tools = {}

    def register(tool):
        tools[tool.__name__] = tool
        return tool

    memory_tools.register(SimpleNamespace(tool=register))
    ctx = SimpleNamespace(
        deps=PhiDeps(
            author_handle="",
            memory=memory,
            notifications_context={"devlog": {"author_handle": "devlog"}},
        )
    )
    return tools["search_memory"], ctx, memory


@pytest.mark.parametrize(
    "options", [{"about": ALI}, {"about": f"@{ALI}"}, {}, {"tag": "correction"}]
)
async def test_memory_search_returns_original_post_references(options):
    tool, ctx, _ = tool_with_memory()
    result = await tool(ctx, query="ten votes", **options)
    assert PARENT in result
    assert REPLY in result
    assert "ten votes" in result


async def test_unified_user_results_keep_references():
    _, _, memory = tool_with_memory()
    result = await memory.search_unified(ALI, "ten votes")
    user = next(row for row in result if row["_source"] == "user")
    assert user["source_uris"] == [PARENT, REPLY]


async def test_default_search_renders_current_author_evidence():
    tool, ctx, memory = tool_with_memory()
    ctx.deps.author_handle = ALI
    memory.namespaces["episodic"] = Namespace([])
    result = await tool(ctx, query="ten votes")
    assert f"[@{ALI} interaction]" in result
    assert PARENT in result
    assert REPLY in result


@pytest.mark.parametrize(
    "options", [{"about": ALI}, {"about": f"@{ALI}"}, {}, {"tag": "correction"}]
)
async def test_legacy_memory_without_references_is_still_readable(options):
    tool, ctx, _ = tool_with_memory(legacy=True)
    result = await tool(ctx, query="ten votes", **options)
    assert "ten votes" in result
    assert "at://" not in result


@pytest.mark.parametrize("legacy", [False, True])
async def test_per_person_context_keeps_evidence(legacy, monkeypatch):
    _, _, memory = tool_with_memory(legacy=legacy)
    monkeypatch.setattr(
        memory, "get_relationship_summary", AsyncMock(return_value=None)
    )
    block = await memory.build_user_context(ALI, "ten votes")
    observations, exchanges = block.split("[PAST EXCHANGES", 1)
    for section in (observations, exchanges):
        assert "ten votes" in section
        assert (PARENT in section) is not legacy
        assert (REPLY in section) is not legacy


@pytest.mark.parametrize("legacy", [False, True])
async def test_recent_context_keeps_evidence_through_reader(legacy, monkeypatch):
    _, _, memory = tool_with_memory(legacy=legacy)
    namespace = memory.get_user_namespace(ALI)
    monkeypatch.setattr(
        memory, "_user_namespace_ids", lambda: ["phi-users-alimabsoute_bsky_social"]
    )
    monkeypatch.setattr(
        memory, "client", SimpleNamespace(namespace=lambda _: namespace), raising=False
    )
    recent = await memory.get_recent_interactions(top_k=3)
    block = render_recent_conversations(recent)
    assert "2026-09-04 @alimabsoute.bsky.social" in block
    assert 'you replied "the cap forces a choice"' in block
    assert (PARENT in block) is not legacy
    assert (REPLY in block) is not legacy


@pytest.mark.parametrize("options", [{"about": ALI}, {"tag": "correction"}, {}])
async def test_backend_failure_never_becomes_no_memories(options):
    tool, ctx, memory = tool_with_memory()
    ctx.deps.author_handle = ALI
    broken = Mock()
    broken.query.side_effect = RuntimeError("backend was not found in routing table")
    memory.get_user_namespace = lambda _: broken
    memory.namespaces["episodic"] = broken
    result = await tool(ctx, query="ten votes", **options)
    assert "incomplete" in result
    assert "read failed" in result
    assert "no memories" not in result
    assert "routing table" not in result


async def test_partial_search_preserves_available_evidence_and_names_missing_scope():
    tool, ctx, memory = tool_with_memory()
    ctx.deps.author_handle = ALI
    broken = Mock()
    broken.query.side_effect = RuntimeError("offline")
    memory.namespaces["episodic"] = broken
    result = await tool(ctx, query="ten votes")
    assert "episodic: read failed" in result
    assert PARENT in result and REPLY in result
    assert "Available results" in result


async def test_missing_namespace_and_successful_empty_search_are_distinct():
    tool, ctx, memory = tool_with_memory()
    memory.namespaces["episodic"] = Namespace([])
    empty = await tool(ctx, query="ten votes")
    assert empty == "no relevant memories found"
    missing = Mock()
    missing.query.side_effect = NotFoundError(
        "namespace absent",
        response=httpx.Response(
            404, request=httpx.Request("POST", "https://memory.test/query")
        ),
        body=None,
    )
    memory.namespaces["episodic"] = missing
    result = await tool(ctx, query="ten votes")
    assert "episodic: namespace missing" in result
    assert "no relevant memories found" not in result


async def test_embedding_failure_is_reported_without_backend_error_text():
    tool, ctx, memory = tool_with_memory()
    memory._get_embedding.side_effect = RuntimeError("provider credentials unavailable")
    result = await tool(ctx, query="ten votes")
    assert "Memory search failed" in result
    assert "credentials" not in result


@pytest.mark.parametrize("options", [{}, {"tag": "correction"}])
async def test_episodic_search_keeps_the_exact_version_id(options):
    tool, ctx, _ = tool_with_memory()
    result = await tool(ctx, query="ten votes", **options)
    assert "[note example-exchange]" in result


@pytest.mark.parametrize("options", [{}, {"about": ALI}, {"about": f"@{ALI}"}])
async def test_search_excludes_replaced_accounts_but_keeps_legacy_records(options):
    tool, ctx, memory = tool_with_memory()
    ctx.deps.author_handle = ALI
    namespace = memory.get_user_namespace(ALI)
    base = namespace.records[0]
    namespace.records = [
        {**base, "id": "old", "status": "superseded", "content": "withdrawn account"},
        {**base, "id": "current", "content": "current account"},
        {
            key: value
            for key, value in {
                **base,
                "id": "legacy",
                "content": "legacy account",
            }.items()
            if key != "status"
        },
    ]
    memory.namespaces["episodic"] = Namespace([])
    result = await tool(ctx, query="account", **options)
    assert "withdrawn account" not in result
    assert "current account" in result
    assert "legacy account" in result
