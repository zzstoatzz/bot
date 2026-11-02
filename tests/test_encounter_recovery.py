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

    def query(*, filters, rank_by, top_k, include_attributes):
        completed = sorted(
            (
                r
                for r in rows.values()
                if r["kind"] == "encounter_scan" and r["status"] == "completed"
            ),
            key=lambda r: r["started_at"],
            reverse=True,
        )
        return Mock(rows=[Mock(model_dump=lambda r=r: r) for r in completed[:top_k]])

    storage = Mock()
    storage.namespace.return_value.write.side_effect = write
    storage.namespace.return_value.query.side_effect = query
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


async def test_scan_stops_where_a_completed_scan_left_off():
    """From 2026-10-20 phi's history passed the twenty-page bound, so every
    scan failed though only 77 events were new. A page reaching what a
    completed scan stored ends the scan."""
    storage, rows = storage_fake()
    client = Mock()
    client.get_notifications = AsyncMock(
        side_effect=[page([1], read=True, indexed="2020-01-01T00:00:00Z")]
    )
    first = await recover_encounters(client, storage, "private-test")
    assert first["status"] == "completed" and first["covered_until"] == ""

    client.get_notifications = AsyncMock(
        side_effect=[
            page([3, 2], "next", indexed="2999-01-01T00:00:00Z"),
            page([1], "older", read=True, indexed="2020-01-01T00:00:00Z"),
            RuntimeError("must not read past covered history"),
        ]
    )
    second = await recover_encounters(client, storage, "private-test", max_pages=2)
    assert second["status"] == "completed"
    assert second["covered_until"] and second["pages_captured"] == 2
    assert client.get_notifications.await_count == 2
    events = {r["content"] for r in rows.values() if r["kind"] == "encounter"}
    assert events == {"event 1", "event 2", "event 3"}


async def test_without_a_completed_scan_the_bound_still_fails_the_scan():
    from bot.services.notification_history import IncompleteNotificationScan

    storage, rows = storage_fake()
    client = Mock()
    client.get_notifications = AsyncMock(return_value=page([1], "next"))
    with pytest.raises(IncompleteNotificationScan):
        await recover_encounters(client, storage, "private-test", max_pages=2)
    scan = next(r for r in rows.values() if r["kind"] == "encounter_scan")
    assert scan["status"] == "failed"
