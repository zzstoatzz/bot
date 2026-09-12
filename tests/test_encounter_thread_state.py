"""Current mute state annotates historical events without rewriting them."""

import copy
import json
from unittest.mock import AsyncMock

from bot.memory.encounters import encounter_thread_states, render_recent_encounters

ROOT = "at://did:plc:someone/app.bsky.feed.post/root"


def recent():
    rows = [
        {
            "id": str(i),
            "actor_handle": "someone.example",
            "actor_did": "did:plc:someone",
            "reason": "reply",
            "indexed_at": "then",
            "captured_at": "then",
            "content": "original words",
            "event_uri": ROOT + str(i),
            "record_json": json.dumps({"reply": {"root": {"uri": ROOT}}}),
        }
        for i in range(2)
    ]
    return {
        "status": "ok",
        "since": "then",
        "until": "now",
        "has_more": False,
        "rows": rows,
    }


async def test_same_thread_checked_once_and_original_records_preserved():
    data = recent()
    original = copy.deepcopy(data)
    read = AsyncMock(return_value=(ROOT, True))
    states = await encounter_thread_states(data, read)
    read.assert_awaited_once_with(ROOT)
    assert data == original
    text = render_recent_encounters(data, states)
    assert text.count("muted; disengaged") == 2
    assert text.count("original words") == 2


async def test_failed_state_read_preserves_history_without_implying_permission():
    data = recent()
    states = await encounter_thread_states(
        data, AsyncMock(side_effect=ValueError("gone"))
    )
    text = render_recent_encounters(data, states)
    assert "unavailable; not permission to contact" in text
    assert "original words" in text


async def test_unmuted_is_not_contact_consent():
    states = await encounter_thread_states(
        recent(), AsyncMock(return_value=(ROOT, False))
    )
    assert set(states.values()) == {"unmuted; contact permissions still apply"}
