"""Observation reconciliation judges every neighbour it fetched.

`_reconcile_observation` read the three nearest active observations and
compared the new one with the nearest only. A fact contradicting the second
or third nearest never superseded it, and both stayed active in the
per-author block.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from bot.memory.extraction import Observation
from bot.memory.namespace_memory import NamespaceMemory

NEIGHBOURS = [
    {
        "id": "nearest",
        "content": "works on prefect",
        "tags": ["work"],
        "created_at": "",
        "source_uris": ["at://a/1"],
    },
    {
        "id": "second",
        "content": "lives in chicago",
        "tags": ["location"],
        "created_at": "",
        "source_uris": ["at://a/2"],
    },
    {
        "id": "third",
        "content": "based in chicago, illinois",
        "tags": ["location"],
        "created_at": "",
        "source_uris": ["at://a/3"],
    },
]


def _memory():
    mem = NamespaceMemory.__new__(NamespaceMemory)
    ns = Mock()
    mem.get_user_namespace = Mock(return_value=ns)
    mem._get_embedding = AsyncMock(return_value=[0.1] * 8)
    mem._find_similar_observations = AsyncMock(return_value=NEIGHBOURS)
    return mem, ns


def _agent(action, targets=(), new_content=None):
    result = Mock()
    result.output.decision = SimpleNamespace(
        action=action,
        reason="r",
        new_content=new_content,
        new_tags=None,
        targets=list(targets),
    )
    agent = Mock()
    agent.run = AsyncMock(return_value=result)
    return agent


def _patched(ns):
    return [
        row
        for call in ns.write.call_args_list
        for row in call.kwargs.get("patch_rows") or []
    ]


def _upserted(ns):
    return [
        row
        for call in ns.write.call_args_list
        for row in call.kwargs.get("upsert_rows") or []
    ]


async def _reconcile(mem, agent, obs):
    with patch(
        "bot.memory.namespace_memory.get_reconciliation_agent", return_value=agent
    ):
        await mem._reconcile_observation("nate.test", obs)


async def test_reconciler_is_shown_every_neighbour():
    mem, _ns = _memory()
    agent = _agent("ADD")
    await _reconcile(mem, agent, Observation(content="moved to berlin"))
    prompt = agent.run.await_args.args[0]
    for n, row in enumerate(NEIGHBOURS, start=1):
        assert f"EXISTING {n}: {row['content']}" in prompt


async def test_contradiction_of_farther_neighbours_supersedes_them():
    mem, ns = _memory()
    obs = Observation(content="moved to berlin", source_uris=["at://a/9"])
    await _reconcile(mem, _agent("DELETE", targets=[2, 3]), obs)
    assert _patched(ns) == [
        {"id": "second", "status": "superseded"},
        {"id": "third", "status": "superseded"},
    ]
    row = _upserted(ns)[0]
    assert row["content"] == "moved to berlin"
    assert row["supersedes"] == "second"
    assert row["source_uris"] == ["at://a/9"]


async def test_supersedes_points_at_the_nearest_named_row_whatever_order_it_was_named():
    mem, ns = _memory()
    await _reconcile(
        mem, _agent("DELETE", targets=[3, 2]), Observation(content="moved to berlin")
    )
    assert [row["id"] for row in _patched(ns)] == ["second", "third"]
    assert _upserted(ns)[0]["supersedes"] == "second"


async def test_update_merges_every_target_and_unions_their_sources():
    mem, ns = _memory()
    obs = Observation(content="in chicago since 2019", source_uris=["at://a/9"])
    await _reconcile(
        mem, _agent("UPDATE", targets=[2, 3], new_content="chicago since 2019"), obs
    )
    assert [row["id"] for row in _patched(ns)] == ["second", "third"]
    row = _upserted(ns)[0]
    assert row["content"] == "chicago since 2019"
    assert row["source_uris"] == ["at://a/2", "at://a/3", "at://a/9"]


async def test_no_targets_falls_back_to_the_nearest():
    mem, ns = _memory()
    await _reconcile(mem, _agent("DELETE"), Observation(content="left prefect"))
    assert _patched(ns) == [{"id": "nearest", "status": "superseded"}]


async def test_noop_writes_nothing():
    mem, ns = _memory()
    await _reconcile(mem, _agent("NOOP", targets=[2]), Observation(content="chicago"))
    ns.write.assert_not_called()
