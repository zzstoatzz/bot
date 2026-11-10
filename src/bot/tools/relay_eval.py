"""relay-eval's public JSON API, read as-is.

relay-eval generates GET /api from the route table that serves its
endpoints, so the index is the API: phi reads it, then asks what she needs.
This tool only fixes the host, allows GET under /api, and bounds the
response; it does not decide which questions about relays exist.
"""

from typing import Annotated

import httpx
from pydantic import Field
from pydantic_ai import RunContext

from bot.config import settings
from bot.tools._helpers import PhiDeps

RESPONSE_CHAR_BUDGET = 24000


def api_url(path: str) -> str | None:
    """The full URL for an /api path on relay-eval, or None if it is not one."""
    if not (path == "/api" or path.startswith("/api/")):
        return None
    if any(part in (".", "..") for part in path.split("/")) or any(
        c in path for c in "?#\\"
    ):
        return None
    return settings.relay_eval_url.rstrip("/") + path


def bounded(text: str) -> str:
    if len(text) <= RESPONSE_CHAR_BUDGET:
        return text
    return (
        text[:RESPONSE_CHAR_BUDGET]
        + f"\n… truncated at {RESPONSE_CHAR_BUDGET:,} of {len(text):,} characters. "
        "narrow the request with the endpoint's parameters (see /api)."
    )


async def read_relay_eval(path: str, params: dict[str, str] | None) -> str:
    url = api_url(path)
    if url is None:
        return "path must be /api or start with /api/ (no query string; use params)"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as http:
            r = await http.get(url, params=params or None)
    except httpx.HTTPError as e:
        return f"relay-eval unreachable: {e}"
    if r.status_code != 200:
        return f"relay-eval answered {r.status_code}: {r.text[:500]}"
    return bounded(r.text)


def register(agent):
    @agent.tool
    async def relay_eval(
        ctx: RunContext[PhiDeps],
        path: Annotated[
            str,
            Field(
                description=(
                    "an endpoint path such as /api/status or /api/runs/123. "
                    "/api (the default) lists every endpoint and the "
                    "parameters each one reads."
                )
            ),
        ] = "/api",
        params: Annotated[
            dict[str, str] | None,
            Field(
                description=(
                    "query parameters for the endpoint, as listed for it in "
                    "/api, e.g. {'name': 'zlay.waow.tech', 'limit': '48'}"
                )
            ),
        ] = None,
    ) -> str:
        """Read relay-eval, which measures how much of the atproto network each relay and Jetstream delivers.

        Start with no arguments to get the endpoint index, which relay-eval
        generates from its own router; each entry says what the numbers
        mean. Responses are JSON exactly as served, cut off at about 24k
        characters.
        """
        return await read_relay_eval(path, params)
