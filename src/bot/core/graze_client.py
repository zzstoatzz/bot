"""Async client for graze.social's undocumented REST API.

Graze serves custom Bluesky feed algorithms. This client handles the full
feed lifecycle: login → create PDS record → register with graze → publish.

API reference: https://whtwnd.com/did:plc:r2whjvupgfw55mllpksnombn/3mgbz7xdeil2h
"""

import logging
from datetime import UTC, datetime

import httpx

from bot.core.atproto_client import bot_client

logger = logging.getLogger("bot.graze_client")

BASE_URL = "https://api.graze.social"
GRAZE_DID = "did:web:api.graze.social"


class GrazeClient:
    def __init__(self, handle: str, password: str):
        self._handle = handle
        self._password = password
        self._cookies: httpx.Cookies | None = None
        self._user_id: int | None = None

    async def _ensure_session(self) -> None:
        """Login to graze if we don't have a valid session."""
        if self._cookies is not None:
            return
        await self._login()

    async def _login(self) -> None:
        """Authenticate with graze and cache the session cookie + user_id."""
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{BASE_URL}/app/login",
                json={"username": self._handle, "password": self._password},
            )
            r.raise_for_status()
            data = r.json()
            self._user_id = data["id"]
            self._cookies = r.cookies
            logger.info(f"graze login ok, user_id={self._user_id}")

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        """Make an authenticated request, re-logging in on 401."""
        await self._ensure_session()
        async with httpx.AsyncClient(
            base_url=BASE_URL, cookies=self._cookies, timeout=30
        ) as client:
            r = await client.request(method, path, **kwargs)
            if r.status_code == 401:
                logger.info("graze session expired, re-logging in")
                self._cookies = None
                await self._login()
                r = await client.request(
                    method,
                    path,
                    cookies=self._cookies,
                    **{k: v for k, v in kwargs.items() if k != "cookies"},
                )
            r.raise_for_status()
            return r

    async def create_feed(
        self,
        rkey: str,
        display_name: str,
        description: str,
        filter_manifest: dict,
    ) -> dict:
        """Create a new graze-powered feed. Full 5-step flow:

        1. putRecord on PDS (app.bsky.feed.generator)
        2. migrate_algo (register filter with graze)
        3. complete_migration
        4. publish_algo
        5. set-publicity to public

        Returns {"uri": ..., "algo_id": ...}.
        """
        # 1. create the feed generator record on phi's PDS
        await bot_client.authenticate()
        assert bot_client.client.me is not None
        did = bot_client.client.me.did
        feed_uri = f"at://{did}/app.bsky.feed.generator/{rkey}"

        bot_client.client.com.atproto.repo.put_record(
            data={
                "repo": did,
                "collection": "app.bsky.feed.generator",
                "rkey": rkey,
                "record": {
                    "$type": "app.bsky.feed.generator",
                    "did": GRAZE_DID,
                    "displayName": display_name,
                    "description": description,
                    "createdAt": datetime.now(UTC).isoformat(),
                },
            }
        )
        logger.info(f"PDS record created: {feed_uri}")

        # 2. register the filter manifest with graze
        r = await self._request(
            "POST",
            "/app/migrate_algo",
            json={
                "user_id": self._user_id,
                "feed_uri": feed_uri,
                "algorithm_manifest": filter_manifest,
            },
        )
        algo_id = r.json()["algo_id"]
        logger.info(f"algo migrated, algo_id={algo_id}")

        # 3. complete migration
        await self._request(
            "POST",
            "/app/complete_migration",
            json={"algo_id": algo_id, "user_id": self._user_id},
        )

        # 4. publish
        await self._request("GET", f"/app/publish_algo/{algo_id}")

        # 5. make public
        await self._request(
            "GET",
            f"/app/api/v1/algorithm-management/set-publicity/{algo_id}/true",
        )

        logger.info(f"feed published: {feed_uri}")
        return {"uri": feed_uri, "algo_id": algo_id}

    async def list_feeds(self) -> list[dict]:
        """List phi's existing graze feeds."""
        r = await self._request("GET", "/app/my_feeds")
        return r.json()

    async def delete_feed(self, algo_id: int) -> None:
        """Delete a graze feed by algo_id."""
        await self._request("DELETE", f"/app/my_feeds/{algo_id}")
        logger.info(f"feed deleted: algo_id={algo_id}")
