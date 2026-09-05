"""Recovery captures already-read history and never claims a partial scan finished."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from bot.memory.encounters import ENCOUNTER_SCHEMA
from bot.services.encounter_recovery import recover_encounters
from tests.test_notification_history import page


def storage_fake():
    rows = {}

    def write(*, upsert_rows, upsert_condition=None, schema=None):
        if upsert_condition:
            assert schema == ENCOUNTER_SCHEMA
        inserted = 0
        for row in upsert_rows:
            if upsert_condition and row["id"] in rows:
                continue
            rows[row["id"]] = dict(row)
            inserted += 1
        return Mock(rows_affected=inserted)

    storage = Mock()
    storage.namespace.return_value.write.side_effect = write
    return storage, rows


async def test_failed_scan_replays_read_pages_and_recovers_late_event():
    storage, rows = storage_fake()
    client = Mock()
    client.get_notifications = AsyncMock(
        side_effect=[page([1], "next", read=True), RuntimeError("offline")]
    )
    with pytest.raises(RuntimeError, match="offline"):
        await recover_encounters(client, storage, "private-test")
    failed = next(r for r in rows.values() if r["kind"] == "encounter_scan")
    assert failed["status"] == "failed"
    assert failed["pages_captured"] == 1
    original = next(r for r in rows.values() if r["kind"] == "encounter")
    client.get_notifications.side_effect = [
        page([2, 1], "next", read=True),
        page([0], read=True),
    ]
    complete = await recover_encounters(client, storage, "private-test")
    assert complete["status"] == "completed"
    assert complete["pages_captured"] == 2
    events = [r for r in rows.values() if r["kind"] == "encounter"]
    assert {r["content"] for r in events} == {"event 0", "event 1", "event 2"}
    assert rows[original["id"]] == original
    client.mark_notifications_seen.assert_not_called()


@pytest.mark.parametrize("failure", [asyncio.CancelledError(), RuntimeError("lost")])
async def test_interrupted_scan_never_records_completion(failure):
    storage, rows = storage_fake()
    client = Mock()
    client.get_notifications = AsyncMock(side_effect=[page([1], "next"), failure])
    with pytest.raises(type(failure)):
        await recover_encounters(client, storage, "private-test")
    scan = next(r for r in rows.values() if r["kind"] == "encounter_scan")
    assert scan["status"] != "completed"
    assert scan["pages_captured"] == 1


async def test_storage_failure_does_not_fetch_next_page_or_claim_completion():
    storage, rows = storage_fake()
    write = storage.namespace.return_value.write.side_effect

    def fail_event(**kwargs):
        if kwargs["upsert_rows"][0]["kind"] == "encounter":
            raise RuntimeError("storage unavailable")
        return write(**kwargs)

    storage.namespace.return_value.write.side_effect = fail_event
    client = Mock()
    client.get_notifications = AsyncMock(return_value=page([1], "next"))
    with pytest.raises(RuntimeError, match="storage unavailable"):
        await recover_encounters(client, storage, "private-test")
    assert client.get_notifications.await_count == 1
    scan = next(iter(rows.values()))
    assert scan["status"] == "failed"
    assert scan["pages_captured"] == 0
