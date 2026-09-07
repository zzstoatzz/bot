"""Corrections target a known version and preserve its history."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.memory.namespace_memory import NamespaceMemory


def memory():
    mem = NamespaceMemory.__new__(NamespaceMemory)
    mem.namespaces = {"episodic": Mock()}
    mem._get_embedding = AsyncMock(return_value=[0.1])
    mem._write_episodic = AsyncMock(return_value={"id": "new"})
    mem._find_similar_episodic = AsyncMock()
    return mem


NOTE = {
    "status": "ok",
    "note": {
        "id": "chosen",
        "status": "active",
        "content": "old",
        "source_uris": ["at://original"],
    },
}


async def test_exact_correction_preserves_text_target_and_sources():
    mem = memory()
    text = "At observation time the final round had not settled."
    with patch("bot.memory.namespace_memory.read_note", AsyncMock(return_value=NOTE)):
        await mem.correct_episodic_memory("chosen", text, ["market"], ["at://new"])
    mem._find_similar_episodic.assert_not_awaited()
    args = mem._write_episodic.await_args
    assert args.args[:4] == (
        text,
        ["market", "correction"],
        "tool:correction",
        ["at://original", "at://new"],
    )
    assert args.kwargs == {"supersedes": "chosen"}


@pytest.mark.parametrize(
    "state",
    [
        {"status": "not_found", "note": None},
        {"status": "unavailable", "note": None},
        {"status": "ok", "note": {**NOTE["note"], "status": "superseded"}},
    ],
)
async def test_bad_target_never_writes(state):
    mem = memory()
    with (
        patch("bot.memory.namespace_memory.read_note", AsyncMock(return_value=state)),
        pytest.raises(ValueError),
    ):
        await mem.correct_episodic_memory("chosen", "replacement", [])
    mem._write_episodic.assert_not_awaited()


async def test_target_changed_during_embedding_is_refused():
    mem = memory()
    changed = {"status": "ok", "note": {**NOTE["note"], "status": "superseded"}}
    with (
        patch(
            "bot.memory.namespace_memory.read_note",
            AsyncMock(side_effect=[NOTE, changed]),
        ),
        pytest.raises(ValueError),
    ):
        await mem.correct_episodic_memory("chosen", "replacement", [])
    mem._write_episodic.assert_not_awaited()
