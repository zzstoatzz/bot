"""Page retrieval for the local encounter-capture prototype.

This reader does not acknowledge notifications or choose what merits a run.
Read flags describe Bluesky UI state, not whether an event was captured.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

from atproto import models

from bot.core.atproto_client import BotClient


class IncompleteNotificationScan(RuntimeError):
    """The traversal hit a structural bound without proving exhaustion."""


async def notification_pages(
    client: BotClient, *, max_pages: int = 100
) -> AsyncIterator[models.AppBskyNotificationListNotifications.Response]:
    """Yield all visible pages, retaining original events and read flags.

    The caller can durably store each page before requesting the next one.
    Failure or a traversal limit propagates; neither implies a completed scan.
    Restart by scanning again and deduplicating durable event identities.
    Exhaustion only describes this API traversal, not delayed or filtered-out
    events, and does not establish a safe acknowledgement timestamp.
    """
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    cursor = None
    visited: set[str] = set()
    for _ in range(max_pages):
        page = await client.get_notifications(limit=100, cursor=cursor, priority=False)
        yield page
        if not page.cursor:
            return
        if page.cursor in visited:
            raise IncompleteNotificationScan(
                "notification cursor repeated; scan incomplete"
            )
        visited.add(page.cursor)
        cursor = page.cursor
    raise IncompleteNotificationScan("notification page limit reached; scan incomplete")


async def visible_unread_notifications(
    client: BotClient,
    *,
    max_pages: int = 100,
    capture: Callable[[list], Awaitable[None]] | None = None,
) -> list[models.AppBskyNotificationListNotifications.Notification]:
    """Collect the visible unread window before dispatching any of it.

    AppView pages newest first and derives read state from a seen timestamp.
    A nonempty, entirely read page ends this live window; an empty page with
    a cursor does not. This is not recovery: another reader or a delayed event
    can change read state independently of capture. Use notification_pages
    without this boundary for recovery scans.
    """
    unread = {}
    async for page in notification_pages(client, max_pages=max_pages):
        if capture and page.notifications:
            await capture(page.notifications)
        for notification in page.notifications:
            if not notification.is_read:
                key = (notification.uri, notification.cid, notification.reason)
                unread.setdefault(key, notification)
        if page.notifications and all(n.is_read for n in page.notifications):
            break
    return list(unread.values())
