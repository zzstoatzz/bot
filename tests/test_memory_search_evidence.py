"""A remembered exchange must let Phi open the original evidence.

The Ali exchange was stored with both post URIs, but memory search dropped
them. Exercise the real search tool and memory readers against a backend
that honors attribute projection, so a renderer-only fix cannot pass.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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
