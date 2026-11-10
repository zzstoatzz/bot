"""relay_eval reads relay-eval's API as served; it only guards the host, method and size."""

from unittest.mock import patch

import httpx
import pytest

from bot.tools import relay_eval
from bot.tools.relay_eval import RESPONSE_CHAR_BUDGET, api_url, read_relay_eval

ORIGIN = "https://relay-eval.waow.tech"


def serve(handler):
    real = httpx.AsyncClient

    def client(**kwargs):
        return real(transport=httpx.MockTransport(handler), **kwargs)

    return patch.object(relay_eval.httpx, "AsyncClient", side_effect=client)


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/apix",
        "/api/../og",
        "/api/./status",
        "/api/status?name=x",
        "https://evil.test/api",
        "api/status",
        "/api\\status",
    ],
)
def test_only_api_paths_on_the_fixed_host(path):
    assert api_url(path) is None


def test_api_paths_resolve_on_relay_eval():
    assert api_url("/api") == f"{ORIGIN}/api"
    assert api_url("/api/runs/12/diffs") == f"{ORIGIN}/api/runs/12/diffs"


async def test_params_are_sent_and_json_comes_back_as_served():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["method"] = request.method
        return httpx.Response(200, text='{"points":[]}')

    with serve(handler):
        out = await read_relay_eval(
            "/api/relays/history", {"name": "zlay.waow.tech", "limit": "48"}
        )
    assert out == '{"points":[]}'
    assert seen == {
        "url": f"{ORIGIN}/api/relays/history?name=zlay.waow.tech&limit=48",
        "method": "GET",
    }


async def test_errors_carry_relay_evals_own_message():
    with serve(
        lambda r: httpx.Response(
            400, text='{"error":"missing required query parameter: name"}'
        )
    ):
        out = await read_relay_eval("/api/relays/history", None)
    assert out.startswith("relay-eval answered 400")
    assert "missing required query parameter: name" in out


async def test_large_responses_are_cut_with_a_way_forward():
    body = "x" * (RESPONSE_CHAR_BUDGET + 10)
    with serve(lambda r: httpx.Response(200, text=body)):
        out = await read_relay_eval("/api/trend", None)
    assert out.startswith("x" * RESPONSE_CHAR_BUDGET)
    assert "truncated" in out and "see /api" in out


async def test_rejected_paths_never_leave_the_process():
    def handler(request):
        raise AssertionError("no request expected")

    with serve(handler):
        out = await read_relay_eval("/og.svg", None)
    assert out.startswith("path must be /api")
