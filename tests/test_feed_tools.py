import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

import pytest
from atproto import Client, models
from pydantic_ai import Agent, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from bot.config import settings
from bot.core import override
from bot.core.atproto_client import BotClient
from bot.tools import feeds
from bot.tools._helpers import PhiDeps

DID = "did:plc:phi"
TARGET = "did:plc:source"


@pytest.fixture
def pds(monkeypatch):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def respond(self, body):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_GET(self):
            url = urlparse(self.path)
            requests.append((url.path, parse_qs(url.query)))
            if url.path.endswith("getFollows"):
                self.respond(
                    {"subject": {"did": DID, "handle": "phi.test"}, "follows": []}
                )
            elif url.path.endswith("resolveHandle"):
                self.respond({"did": TARGET})
            elif url.path.endswith("getRecord"):
                self.respond({"value": {"active": False}})
            else:
                self.respond({"feed": []})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, body))
            self.respond(
                {"uri": f"at://{DID}/app.bsky.graph.follow/one", "cid": "bafyreitest"}
            )

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    bot = BotClient.__new__(BotClient)
    bot.client = Client(base_url=url)
    bot.client.me = models.AppBskyActorDefs.ProfileViewDetailed(
        did=DID, handle="phi.test"
    )
    bot._authenticated = True
    monkeypatch.setattr(feeds, "bot_client", bot)
    monkeypatch.setattr(override, "_pds_cache", url)
    monkeypatch.setattr(override, "_cache", {"override": None, "fetched_at": 0.0})
    monkeypatch.setattr(settings, "saved_feeds", {})
    yield requests
    server.shutdown()
    server.server_close()
    thread.join()


def tool(name):
    agent = Agent("test")
    feeds.register(agent)
    return agent._function_toolset.tools[name].function


def context(author):
    return RunContext(
        deps=PhiDeps(author_handle=author), model=TestModel(), usage=RunUsage()
    )


async def test_empty_timeline_uses_following_reader(pds):
    result = await tool("read_feed")(context("reader.test"))
    assert "timeline is empty" in result
    assert "following" in result
    assert pds == [("/xrpc/app.bsky.feed.getTimeline", {"limit": ["20"]})]


async def test_custom_feed_resolves_own_slug(pds):
    assert (
        await tool("read_feed")(context("reader.test"), "jazz-vibes")
        == "no posts in this feed yet"
    )
    assert pds == [
        (
            "/xrpc/app.bsky.feed.getFeed",
            {
                "feed": [f"at://{DID}/app.bsky.feed.generator/jazz-vibes"],
                "limit": ["20"],
            },
        )
    ]


async def test_follow_owner_gate_precedes_network(pds):
    result = await tool("follow_user")(context("stranger.test"), "source.test")
    assert settings.owner_handle in result
    assert pds == []


async def test_authorized_follow_reaches_real_sdk_write(pds):
    result = await tool("follow_user")(context(settings.owner_handle), "source.test")
    assert "now following @source.test" in result
    path, body = pds[-1]
    assert path == "/xrpc/com.atproto.repo.createRecord"
    assert body["repo"] == DID
    assert body["collection"] == "app.bsky.graph.follow"
    assert body["record"]["subject"] == TARGET
