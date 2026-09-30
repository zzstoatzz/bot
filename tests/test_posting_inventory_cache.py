"""The posting inventory compiles once per latest post, across renders and restarts.

After a restart on 2026-09-30 the startup render and two diagnostic renders
each compiled it: three paid calls in six seconds for the same ten posts.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.core import self_state


def _client(latest: str = "at://phi/post/2"):
    posts = [
        SimpleNamespace(
            post=SimpleNamespace(uri=latest, record=SimpleNamespace(text="newest"))
        ),
        SimpleNamespace(
            post=SimpleNamespace(
                uri="at://phi/post/1", record=SimpleNamespace(text="older")
            )
        ),
    ]
    return SimpleNamespace(get_own_posts=AsyncMock(return_value=posts))


@pytest.fixture(autouse=True)
def _inventory_store(tmp_path, monkeypatch):
    monkeypatch.setattr(self_state, "INVENTORY_CACHE_FILE", tmp_path / "inventory.json")
    monkeypatch.setattr(self_state, "_inventory_cache", None)
    self_state._inventory_inflight.clear()
    yield
    self_state._inventory_inflight.clear()


async def test_overlapping_renders_share_one_compile():
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def slow_compile(posts: list[str]) -> str:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return "subjects: things"

    client = _client()
    with patch.object(self_state, "_compile_inventory", slow_compile):
        first = asyncio.create_task(self_state.get_inventory_block(client))
        await started.wait()
        second = asyncio.create_task(self_state.get_inventory_block(client))
        await asyncio.sleep(0)
        release.set()
        a, b = await asyncio.gather(first, second)

    assert calls == 1
    assert a == b and a.endswith("subjects: things")


async def test_restart_reuses_the_saved_inventory(monkeypatch):
    with patch.object(
        self_state, "_compile_inventory", AsyncMock(return_value="subjects: a")
    ):
        await self_state.get_inventory_block(_client())

    monkeypatch.setattr(self_state, "_inventory_cache", None)
    compile_ = AsyncMock(return_value="subjects: b")
    with patch.object(self_state, "_compile_inventory", compile_):
        block = await self_state.get_inventory_block(_client())

    assert compile_.await_count == 0
    assert block.endswith("subjects: a")


async def test_new_post_recompiles():
    with patch.object(
        self_state, "_compile_inventory", AsyncMock(return_value="subjects: a")
    ):
        await self_state.get_inventory_block(_client())

    compile_ = AsyncMock(return_value="subjects: b")
    with patch.object(self_state, "_compile_inventory", compile_):
        block = await self_state.get_inventory_block(_client("at://phi/post/3"))

    assert compile_.await_count == 1
    assert block.endswith("subjects: b")
