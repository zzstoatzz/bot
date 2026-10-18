"""Notifications and replies in atproto apps forked from Bluesky.

A fork like Delvetown keeps Bluesky's shapes under its own namespace
(`town.delve.feed.post`, `town.delve.notification.listNotifications`) and runs
its own AppView, so Bluesky's notification list never carries what happens
there. Each app in `settings.notification_apps` gets a view that reads its
AppView through phi's PDS proxy and hands back the Bluesky SDK models, so the
batch pipeline handles its events like any other. The AT-URIs keep the app's
collection, which is how every later step knows where an event came from and
where a reply to it belongs.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from atproto import models
from atproto_client.models.dot_dict import DotDict

from bot.config import settings
from bot.core.atproto_client import BotClient, bot_client
from bot.core.ops_log import record_local_write
from bot.core.rich_text import create_facets

logger = logging.getLogger("bot.fork_appview")


@dataclass(frozen=True)
class ForkApp:
    namespace: str  # "town.delve"
    name: str  # "delve.town", how phi and the operator name it
    service: str  # proxy target for its AppView methods

    @property
    def post_collection(self) -> str:
        return f"{self.namespace}.feed.post"


def fork_apps() -> list[ForkApp]:
    return [
        ForkApp(namespace=namespace, name=name, service=service)
        for namespace, (name, service) in settings.notification_apps.items()
    ]


def app_for_uri(uri: str) -> ForkApp | None:
    """The fork app whose namespace holds this AT-URI's collection, or None (Bluesky)."""
    parts = uri.removeprefix("at://").split("/")
    if len(parts) < 2:
        return None
    collection = parts[1]
    return next(
        (a for a in fork_apps() if collection.startswith(f"{a.namespace}.")), None
    )


def _retype(value: Any, old: str, new: str) -> Any:
    """Rewrite `$type` values from one namespace to another, leaving data alone."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "$type" and isinstance(item, str) and item.startswith(old):
                out[key] = new + item.removeprefix(old)
            else:
                out[key] = _retype(item, old, new)
        return out
    if isinstance(value, list):
        return [_retype(item, old, new) for item in value]
    return value


def as_bluesky(value: Any, app: ForkApp) -> Any:
    """`town.delve.feed.defs#postView` -> `app.bsky.feed.defs#postView`, recursively."""
    return _retype(value, f"{app.namespace}.", "app.bsky.")


def as_app(value: Any, app: ForkApp) -> Any:
    """The inverse of as_bluesky, for records phi writes into the app."""
    return _retype(value, "app.bsky.", f"{app.namespace}.")


class ForkAppView:
    """The slice of BotClient the notification pipeline reads, for one fork app."""

    def __init__(self, app: ForkApp, client: BotClient = bot_client):
        self.app = app
        self.client = client

    def _call(self, kind: str, method: str, arguments: dict[str, Any]) -> Any:
        proxied = self.client.client.clone()
        proxied.request.set_additional_headers({"atproto-proxy": self.app.service})
        nsid = f"{self.app.namespace}.{method}"
        if kind == "query":
            # the SDK accepts a DotDict here at runtime; its annotation
            # names only its own generated params models
            response = proxied.invoke_query(nsid, params=DotDict(arguments))  # ty: ignore[invalid-argument-type]
        else:
            response = proxied.invoke_procedure(
                nsid,
                content=json.dumps(arguments).encode(),
                headers={"Content-Type": "application/json"},
            )
        return response.content

    async def _query(self, method: str, arguments: dict[str, Any]) -> dict:
        await self.client.authenticate()
        content = await asyncio.to_thread(self._call, "query", method, arguments)
        if not isinstance(content, dict):
            raise ValueError(f"{self.app.name} {method} returned no JSON")
        return as_bluesky(content, self.app)

    async def get_notifications(
        self,
        limit: int = 50,
        *,
        cursor: str | None = None,
        priority: bool | None = None,
    ) -> models.AppBskyNotificationListNotifications.Response:
        arguments: dict[str, Any] = {"limit": limit}
        if cursor:
            arguments["cursor"] = cursor
        if priority is not None:
            arguments["priority"] = priority
        page = await self._query("notification.listNotifications", arguments)
        return models.AppBskyNotificationListNotifications.Response.model_validate(page)

    async def mark_notifications_seen(self, seen_at: str) -> None:
        await self.client.authenticate()
        await asyncio.to_thread(
            self._call, "procedure", "notification.updateSeen", {"seenAt": seen_at}
        )

    async def get_posts(self, uris: list[str]):
        page = await self._query("feed.getPosts", {"uris": uris})
        return models.AppBskyFeedGetPosts.Response.model_validate(page)

    async def get_thread(self, uri: str, depth: int = 10):
        page = await self._query("feed.getPostThread", {"uri": uri, "depth": depth})
        return models.AppBskyFeedGetPostThread.Response.model_validate(page)


def fork_views(client: BotClient = bot_client) -> list[ForkAppView]:
    return [ForkAppView(app, client) for app in fork_apps()]


async def create_app_reply(
    app: ForkApp,
    text: str,
    parent: dict[str, str],
    root: dict[str, str],
    allowed_handles: set[str],
):
    """Write a reply into the app the parent lives in, on phi's own repo.

    Facets are built the way Bluesky posts build them (only allowlisted
    handles become notifying mentions), then moved into the app's namespace.
    """
    await bot_client.authenticate()
    me = bot_client.client.me
    if me is None:
        raise ValueError("authenticated profile unavailable")
    record: dict[str, Any] = {
        "$type": app.post_collection,
        "text": text,
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "reply": {"root": root, "parent": parent},
    }
    facets = create_facets(text, bot_client.client, allowed_handles)
    if facets:
        record["facets"] = as_app(facets, app)
    result = bot_client.client.com.atproto.repo.create_record(
        data={"repo": me.did, "collection": app.post_collection, "record": record}
    )
    record_local_write(result.uri)
    return result
