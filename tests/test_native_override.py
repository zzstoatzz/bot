import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

import pytest
from atproto import Client, models
from pydantic_ai import Agent, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from bot.config import settings
from bot.core import mentionable, override, self_record
from bot.core.atproto_client import BotClient
from bot.tools import bluesky, feeds, goals
from bot.tools import self_record as self_tools
from bot.tools._helpers import PhiDeps

DID = "did:plc:phi"


@pytest.fixture
def pds(monkeypatch):
    state: dict = {"active": True, "message": "hold public writes", "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def respond(self, body):
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            state["requests"].append((url.path, query))
            collection = query.get("collection", [""])[0]
            if url.path.endswith("listRecords"):
                self.respond({"records": []})
            else:
                value = (
                    {"active": state["active"], "message": state["message"]}
                    if collection == override.COLLECTION
                    else {"self": "I read closely."}
                )
                self.respond(
                    {
                        "uri": f"at://{DID}/{collection}/self",
                        "cid": "bafyreitest",
                        "value": value,
                    }
                )

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append((self.path, body))
            self.respond(
                {
                    "uri": f"at://{DID}/io.zzstoatzz.phi.persona/self",
                    "cid": "bafyreitest",
                }
            )

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(override, "_pds_cache", url)
    monkeypatch.setattr(override, "_cache", {"override": None, "fetched_at": 0.0})
    monkeypatch.setattr(self_record, "_cache", {"text": "", "fetched_at": 0.0})
    bot = BotClient.__new__(BotClient)
    bot.client = Client(base_url=url)
    bot.client.me = models.AppBskyActorDefs.ProfileViewDetailed(
        did=DID, handle="phi.test"
    )
    bot._authenticated = True
    for module in (bluesky, feeds, goals, self_tools, mentionable):
        monkeypatch.setattr(module, "bot_client", bot)
    yield state
    server.shutdown()
    server.server_close()
    thread.join()


def tool(name):
    agent = Agent("test")
    goals.register(agent)
    self_tools.register(agent)
    bluesky.register(agent)
    feeds.register(agent)
    return agent._function_toolset.tools[name].function


def context():
    return RunContext(
        deps=PhiDeps(author_handle=settings.owner_handle),
        model=TestModel(),
        usage=RunUsage(),
    )


@pytest.mark.parametrize(
    "name,args",
    [
        (
            "propose_goal_change",
            {"title": "Read", "description": "Read sources", "metabolism": "weekly"},
        ),
        (
            "update_goal_progress",
            {
                "rkey": "one",
                "current_state": "reading",
                "next_step": "compare",
                "last_step": "read",
            },
        ),
        ("write_self", {"text": "I read closely."}),
        ("persona", {"action": "try", "text": "A patient reader."}),
        ("persona", {"action": "drop"}),
        ("follow_user", {"handle": "source.test", "subscribe_posts": True}),
        ("manage_account", {"setting": "labels", "action": "add", "value": "bot"}),
        ("manage_account", {"setting": "labels", "action": "remove", "value": "bot"}),
        (
            "manage_account",
            {"setting": "mentionable", "action": "add", "value": "friend.test"},
        ),
        (
            "manage_account",
            {"setting": "mentionable", "action": "remove", "value": "friend.test"},
        ),
    ],
)
async def test_public_writes_stop_at_operator_record(pds, name, args):
    ctx = context()
    ctx.deps.run_cache["write_self_review"] = "shown"
    result = await tool(name)(ctx, **args)
    assert "hold public writes" in result
    assert "was not performed" in result
    assert pds["requests"] == [
        (
            "/xrpc/com.atproto.repo.getRecord",
            {
                "repo": [settings.owner_did],
                "collection": [override.COLLECTION],
                "rkey": ["self"],
            },
        )
    ]


async def test_reads_and_self_review_remain_available(pds):
    assert "no goals set" == await tool("list_goals")(context())
    result = await tool("write_self")(context(), "new draft")
    assert "not written yet" in result
    assert "I read closely." in result
    assert all(override.COLLECTION not in str(request) for request in pds["requests"])
    assert all(
        path.endswith(("getRecord", "listRecords")) for path, _ in pds["requests"]
    )


async def test_persona_remains_phi_owned_and_expiring_when_override_lifts(pds):
    pds["active"] = False
    ctx = context()
    ctx.deps.author_handle = "not-the-operator.test"
    assert "persona on for 3d" in await tool("persona")(ctx, "try", "A patient reader.")
    path, body = pds["requests"][-1]
    assert path.endswith("putRecord")
    record = body["record"]
    assert datetime.fromisoformat(record["expiresAt"]) - datetime.fromisoformat(
        record["adoptedAt"]
    ) == timedelta(days=3)
    assert "persona dropped" == await tool("persona")(ctx, "drop")
    assert pds["requests"][-1][0].endswith("deleteRecord")
