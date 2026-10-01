import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from atproto_client.exceptions import BadRequestError
from atproto_client.models.common import XrpcError
from atproto_client.models.utils import get_model_as_dict
from atproto_client.request import Response
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from bot.core import xrpc as core
from bot.core.xrpc import authority_domain, service_for, split_nsid
from bot.tools import xrpc
from bot.tools._helpers import PhiDeps

DELVE = "did:web:api.delve.town#bsky_appview"
INACTIVE = {"active": False, "message": ""}
CTX = SimpleNamespace(deps=PhiDeps(author_handle=""))


def tools() -> dict:
    registered = {}
    xrpc.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    return registered


def lexicon(main: dict) -> dict:
    return {
        "uri": "at://x",
        "authority": "did:plc:x",
        "schema": {"defs": {"main": main}},
    }


class FakeClient:
    """Records what the SDK client is asked to send."""

    def __init__(self, error: Exception | None = None):
        self.calls: list = []
        self.error = error
        self.request = SimpleNamespace(set_additional_headers=self.calls.append)

    def clone(self):
        return self

    def invoke_query(self, nsid, params=None):
        # the real client rejects a plain dict here
        sent = get_model_as_dict(params) if params is not None else None
        return self._record("query", nsid, {"params": sent})

    def invoke_procedure(self, nsid, **sent):
        return self._record("procedure", nsid, sent)

    def _record(self, kind, nsid, sent):
        self.calls.append((kind, nsid, sent))
        if self.error:
            raise self.error
        return Response(
            success=True, status_code=200, content={"enabled": True}, headers={}
        )


def test_tools_register_with_real_agent():
    agent = Agent(TestModel(), deps_type=PhiDeps)
    xrpc.register(agent)
    assert {"describe_lexicon", "call_xrpc"} <= set(agent._function_toolset.tools)


def test_authority_domain_reverses_all_but_the_name():
    assert authority_domain("town.delve.membership.join") == "membership.delve.town"
    assert split_nsid("town.delve.membership.defs#membership") == (
        "town.delve.membership.defs",
        "membership",
    )
    with pytest.raises(ValueError):
        split_nsid("https://delve.town")


def test_only_enabled_methods_have_a_service():
    assert service_for("town.delve.membership.join") == DELVE
    assert service_for("town.delve.notification.registerPush") is None
    assert service_for("town.delve.membership") is None


@pytest.mark.parametrize(
    "nsid",
    [
        "com.atproto.server.deleteAccount",
        "chat.bsky.convo.listConvos",
        "town.delve.notification.registerPush",
        "town.delve.graph.getMutes",
        "example.unknown.thing.do",
    ],
)
async def test_a_method_that_is_not_enabled_is_never_called(nsid):
    with (
        patch.object(xrpc, "call_method", AsyncMock()) as call,
        patch.object(xrpc, "get_override", AsyncMock(return_value=INACTIVE)),
    ):
        result = await tools()["call_xrpc"](CTX, nsid)
    assert "Nothing was called" in result
    assert "town.delve.membership.join" in result
    call.assert_not_awaited()


async def test_a_procedure_is_logged_and_a_query_is_not():
    for kind, logged in (("procedure", 1), ("query", 0)):
        output = {"kind": kind, "ok": True, "status": 200, "output": {}}
        with (
            patch.object(xrpc, "call_method", AsyncMock(return_value=output)),
            patch.object(xrpc, "get_override", AsyncMock(return_value=INACTIVE)),
            patch.object(xrpc.logfire, "info") as info,
        ):
            await tools()["call_xrpc"](CTX, "town.delve.membership.join", {"a": 1})
        assert info.call_count == logged
    assert info.call_count == 0


async def test_override_stops_an_enabled_call():
    paused = {"active": True, "message": "operator paused actions"}
    with (
        patch.object(xrpc, "call_method", AsyncMock()) as call,
        patch.object(xrpc, "get_override", AsyncMock(return_value=paused)),
    ):
        result = await tools()["call_xrpc"](CTX, "town.delve.membership.join")
    assert "operator paused actions" in result
    call.assert_not_awaited()


async def test_enabled_call_reaches_its_configured_service():
    output = {"kind": "procedure", "ok": True, "status": 200, "output": {"a": 1}}
    with (
        patch.object(xrpc, "call_method", AsyncMock(return_value=output)) as call,
        patch.object(xrpc, "get_override", AsyncMock(return_value=INACTIVE)),
    ):
        result = await tools()["call_xrpc"](
            CTX, "town.delve.membership.join", {"inviteCode": "abc"}
        )
    call.assert_awaited_once_with(
        "town.delve.membership.join", {"inviteCode": "abc"}, DELVE
    )
    assert json.loads(result) == {
        "nsid": "town.delve.membership.join",
        "service": DELVE,
        **output,
    }


@pytest.mark.parametrize(
    ("main", "arguments", "sent"),
    [
        ({"type": "query"}, None, ("query", {"params": None})),
        ({"type": "query"}, {"limit": 5}, ("query", {"params": {"limit": 5}})),
        ({"type": "procedure"}, None, ("procedure", {})),
        (
            {"type": "procedure", "input": {"encoding": "application/json"}},
            None,
            (
                "procedure",
                {"content": b"{}", "headers": {"Content-Type": "application/json"}},
            ),
        ),
        (
            {"type": "procedure", "input": {"encoding": "application/json"}},
            {"inviteCode": "x"},
            (
                "procedure",
                {
                    "content": b'{"inviteCode": "x"}',
                    "headers": {"Content-Type": "application/json"},
                },
            ),
        ),
    ],
    ids=["query", "query params", "bare procedure", "empty input", "input"],
)
async def test_the_lexicon_decides_what_is_sent(main, arguments, sent):
    client = FakeClient()
    with (
        patch.object(core, "fetch_lexicon", AsyncMock(return_value=lexicon(main))),
        patch.object(core.bot_client, "client", client),
        patch.object(core.bot_client, "authenticate", AsyncMock()),
    ):
        result = await core.call_method("town.delve.x.y", arguments, DELVE)
    assert client.calls == [
        {"atproto-proxy": DELVE},
        (sent[0], "town.delve.x.y", sent[1]),
    ]
    assert result == {
        "kind": sent[0],
        "ok": True,
        "status": 200,
        "output": {"enabled": True},
    }


async def test_a_record_lexicon_is_not_callable():
    client = FakeClient()
    with (
        patch.object(
            core, "fetch_lexicon", AsyncMock(return_value=lexicon({"type": "record"}))
        ),
        patch.object(core.bot_client, "client", client),
        pytest.raises(LookupError, match="not a method"),
    ):
        await core.call_method("town.delve.feed.post", None, DELVE)
    assert client.calls == []


def test_a_service_error_comes_back_as_data():
    error = BadRequestError(
        Response(
            success=False,
            status_code=400,
            content=XrpcError(error="InvalidInvite", message="no invite"),
            headers={},
        )
    )
    with patch.object(core.bot_client, "client", FakeClient(error)):
        result = core._invoke("procedure", "town.delve.membership.join", {}, DELVE)
    assert result == {
        "ok": False,
        "status": 400,
        "error": "InvalidInvite",
        "message": "no invite",
    }


async def test_describe_lexicon_returns_one_definition():
    published = {
        "uri": "at://did:plc:x/com.atproto.lexicon.schema/town.delve.membership.defs",
        "authority": "did:plc:x",
        "schema": {
            "id": "town.delve.membership.defs",
            "defs": {"membership": {"type": "object"}, "other": {"type": "object"}},
        },
    }
    with patch.object(xrpc, "fetch_lexicon", AsyncMock(return_value=published)):
        result = await tools()["describe_lexicon"](
            CTX, "town.delve.membership.defs#membership"
        )
        assert list(json.loads(result)["schema"]["defs"]) == ["membership"]
        missing = await tools()["describe_lexicon"](
            CTX, "town.delve.membership.defs#nope"
        )
    assert "['membership', 'other']" in missing


async def test_describe_lexicon_reports_an_unpublished_namespace():
    with patch.object(
        xrpc, "fetch_lexicon", AsyncMock(side_effect=LookupError("no TXT record"))
    ):
        result = await tools()["describe_lexicon"](CTX, "example.unknown.thing.do")
    assert "no TXT record" in result
