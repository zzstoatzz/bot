"""Async client for graze.social's undocumented REST API.

Lists existing custom feeds for the owned-feeds context block. Feed authoring
was retired on October 2; reading those feeds remains available.

API reference: https://whtwnd.com/did:plc:r2whjvupgfw55mllpksnombn/3mgbz7xdeil2h
"""

import logging

import httpx

logger = logging.getLogger("bot.graze_client")

BASE_URL = "https://api.graze.social"


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
            self._user_id = data["user"]["id"]
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

    async def list_feeds(self) -> list[dict]:
        """List phi's existing graze feeds."""
        r = await self._request("GET", "/app/my_feeds")
        data = r.json()
        return data.get("user_algos", data) if isinstance(data, dict) else data
