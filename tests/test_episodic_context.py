"""Ambient selection cannot rewrite or manufacture the saved evidence."""

import json
from unittest.mock import AsyncMock

import pytest

from bot.memory import namespace_memory
from bot.memory.episodic_context import render_selected_notes


def notes():
    return [
        {
            "id": "saved-qualification",
            "content": "Codex checked one page. No reply was found in that page; I did not perform this read.",
            "created_at": "2026-09-05T17:00:00Z",
            "source": "tool",
            "tags": ["correction"],
            "source_uris": ["at://did:plc:devlog/app.bsky.feed.post/check"],
        }
    ]


def test_qualification_actor_and_record_address_survive_verbatim():
    raw = notes()
    rendered = render_selected_notes(raw, [raw[0]["id"]])
    entry = json.loads(rendered.splitlines()[1])
    assert entry["content"] == raw[0]["content"]
    assert entry["note_id"] == raw[0]["id"]
    assert entry["saved_at"] == raw[0]["created_at"]
    assert entry["tags"] == ["correction"]
    assert entry["stored_source_count"] == 1


@pytest.mark.parametrize(
    "ids", [["invented"], ["saved-qualification", "saved-qualification"]]
)
def test_selection_cannot_invent_or_duplicate_notes(ids):
    with pytest.raises(ValueError):
        render_selected_notes(notes(), ids)


def test_irrelevant_and_absent_notes_render_empty():
    assert render_selected_notes(notes(), []) == ""
    assert render_selected_notes([], []) == ""


async def test_failed_selection_is_distinct_from_no_relevant_memories(monkeypatch):
    memory = namespace_memory.NamespaceMemory.__new__(namespace_memory.NamespaceMemory)
    memory.search_episodic = AsyncMock(return_value=notes())
    monkeypatch.setattr(
        namespace_memory,
        "select_episodic_context",
        AsyncMock(side_effect=RuntimeError("model unavailable")),
    )
    result = await memory.get_episodic_context("which page was checked?")
    assert "selection unavailable" in result
    assert "search_memory" in result
    assert notes()[0]["content"] not in result


async def test_empty_search_does_not_call_selection(monkeypatch):
    memory = namespace_memory.NamespaceMemory.__new__(namespace_memory.NamespaceMemory)
    memory.search_episodic = AsyncMock(return_value=[])
    selection = AsyncMock()
    monkeypatch.setattr(namespace_memory, "select_episodic_context", selection)
    assert await memory.get_episodic_context("something unrelated") == ""
    selection.assert_not_awaited()
