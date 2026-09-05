"""Recovery scans must not confuse UI read state with durable capture."""

from unittest.mock import AsyncMock, Mock

import pytest
from atproto import models

from bot.core.atproto_client import BotClient
from bot.services.notification_history import (
    notification_pages,
    visible_unread_notifications,
)


def page(numbers=(), cursor=None, *, read=False):
    return models.AppBskyNotificationListNotifications.Response.model_validate(
        {
            "cursor": cursor,
            "notifications": [
                {
                    "uri": f"at://did:plc:alice/app.bsky.feed.post/{number}",
                    "cid": "bafyreicaafen4qlk56o5yby5bykss5cwbf5lodep62dnw5alwft4mwrnhq",
                    "author": {"did": "did:plc:alice", "handle": "alice.test"},
                    "reason": "mention",
                    "indexedAt": "2026-09-05T00:00:00Z",
                    "isRead": read,
                    "record": {
                        "$type": "app.bsky.feed.post",
                        "text": f"event {number}",
                        "createdAt": "2026-09-05T00:00:00Z",
                    },
                }
                for number in numbers
            ],
        }
    )


async def test_read_events_and_empty_intermediate_pages_do_not_end_scan():
    client = Mock(spec=BotClient)
    client.get_notifications = AsyncMock(
        side_effect=[
            page(range(100), "second", read=True),
            page(cursor="third"),
            page(range(100, 175)),
        ]
    )
    found = [item async for item in notification_pages(client)]
    assert sum(len(item.notifications) for item in found) == 175
    assert found[0].notifications[0].is_read
    assert [call.kwargs for call in client.get_notifications.await_args_list] == [
        {"limit": 100, "cursor": cursor, "priority": False}
        for cursor in (None, "second", "third")
    ]


async def test_page_failure_keeps_partial_capture_replayable_on_restart():
    client = Mock(spec=BotClient)
    client.get_notifications = AsyncMock(
        side_effect=[page(range(100), "second"), RuntimeError("connection lost")]
    )
    stored = set()

    async def capture_scan():
        async for item in notification_pages(client):
            stored.update((n.uri, n.cid, n.reason) for n in item.notifications)

    with pytest.raises(RuntimeError, match="connection lost"):
        await capture_scan()
    assert len(stored) == 100
    # Another reader can mark these read while Phi is stopped. Replayed event
    # identities still deduplicate; UI read state cannot hide the remaining 75.
    client.get_notifications.side_effect = [
        page(range(100), "second", read=True),
        page(range(100, 175), read=True),
    ]
    await capture_scan()
    assert len(stored) == 175


@pytest.mark.parametrize(
    ("responses", "max_pages", "error"),
    [
        ([page(cursor="same"), page(cursor="same")], 100, "cursor repeated"),
        (
            [page(cursor="a"), page(cursor="b"), page(cursor="a")],
            100,
            "cursor repeated",
        ),
        ([page(cursor="more")], 1, "page limit"),
    ],
)
async def test_incomplete_traversal_is_never_reported_as_exhausted(
    responses, max_pages, error
):
    client = Mock(spec=BotClient)
    client.get_notifications = AsyncMock(side_effect=responses)
    with pytest.raises(RuntimeError, match=error):
        _ = [item async for item in notification_pages(client, max_pages=max_pages)]


async def test_delayed_visible_read_event_is_recovered_by_a_later_scan():
    client = Mock(spec=BotClient)
    client.get_notifications = AsyncMock(
        side_effect=[page([1]), page([2, 1], read=True)]
    )
    first = [item async for item in notification_pages(client)]
    later = [item async for item in notification_pages(client)]
    assert len(first[0].notifications) == 1
    assert {n.record.text for n in later[0].notifications} == {"event 1", "event 2"}


async def test_client_passes_explicit_paging_and_priority_to_sdk():
    client = BotClient.__new__(BotClient)
    client.authenticate = AsyncMock()
    client.client = Mock()
    await client.get_notifications(limit=100, cursor="next", priority=False)
    params = client.client.app.bsky.notification.list_notifications.call_args.kwargs[
        "params"
    ]
    assert params.limit == 100
    assert params.cursor == "next"
    assert params.priority is False
    assert params.seen_at is None


async def test_live_window_crosses_empty_page_and_deduplicates_overlap():
    client = Mock(spec=BotClient)
    client.get_notifications = AsyncMock(
        side_effect=[
            page([3, 2], "second"),
            page(cursor="third"),
            page([2, 1], "fourth"),
            page([0], "older-history", read=True),
        ]
    )
    found = await visible_unread_notifications(client)
    assert [n.record.text for n in found] == ["event 3", "event 2", "event 1"]
    assert client.get_notifications.await_count == 4


async def test_live_page_is_captured_before_read_state_can_hide_events():
    client = Mock(spec=BotClient)
    delivered = page([1, 2], "older", read=True)
    client.get_notifications = AsyncMock(return_value=delivered)
    capture = AsyncMock()
    unread = await visible_unread_notifications(client, capture=capture)
    assert unread == []
    capture.assert_awaited_once_with(delivered.notifications)
    assert client.get_notifications.await_count == 1
