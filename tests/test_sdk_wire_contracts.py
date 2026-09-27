import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from atproto import Client, models
from turbopuffer import Turbopuffer

from bot.core.atproto_client import BotClient
from bot.core.chicken_strategy import Heuristic, read_catalog, write_rule
from bot.memory.namespace_memory import NamespaceMemory

DID = "did:plc:phi"
COLLECTION = "io.zzstoatzz.phi.strategy"


@pytest.fixture
def server():
    requests = []
    records = {
        "topchicken": {
            "$type": COLLECTION,
            "game": "topchicken",
            "doctrine": "Recap stays explicit.\nRULE 45 (baseline): compare earlier evidence.\nRULE 46 (exit): act on the trigger.",
        }
    }

    class Handler(BaseHTTPRequestHandler):
        def respond(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            requests.append((url.path, parse_qs(url.query)))
            if url.path.endswith("listRecords"):
                self.respond(
                    {
                        "records": [
                            {
                                "uri": f"at://{DID}/{COLLECTION}/{key}",
                                "cid": "bafyreitest",
                                "value": value,
                            }
                            for key, value in records.items()
                        ]
                    }
                )
            else:
                self.respond({"namespaces": [{"id": "phi-users-alice_test"}]})

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, data))
            if self.path.endswith("putRecord"):
                records[data["rkey"]] = data["record"]
                self.respond(
                    {
                        "uri": f"at://{DID}/{COLLECTION}/{data['rkey']}",
                        "cid": "bafyreitest",
                    }
                )
            elif self.path.endswith("/query"):
                assert data["filters"] == ["kind", "Eq", "interaction"]
                self.respond(
                    {
                        "rows": [
                            {
                                "id": "one",
                                "content": "completed exchange",
                                "created_at": "2026-09-25T00:00:00Z",
                            }
                        ]
                    }
                )
            else:
                self.respond({})

        def log_message(self, format: str, *args: object) -> None:
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{http.server_port}", requests, records
    http.shutdown()
    http.server_close()
    thread.join()


def bot_at(url):
    bot = BotClient.__new__(BotClient)
    bot.client = Client(base_url=url)
    bot.client.me = models.AppBskyActorDefs.ProfileViewDetailed(
        did=DID, handle="phi.test"
    )
    bot._authenticated = True
    return bot


async def test_notification_timestamp_serializes_to_wire_alias(server):
    url, requests, _ = server
    await bot_at(url).mark_notifications_seen("2026-09-26T00:00:00Z")
    assert requests == [
        ("/xrpc/app.bsky.notification.updateSeen", {"seenAt": "2026-09-26T00:00:00Z"})
    ]


async def test_rule_update_preserves_catalog_and_retirement_overrides_legacy(server):
    url, requests, records = server
    bot = bot_at(url)
    original = dict(records["topchicken"])
    rules, legacy = await read_catalog(bot)
    assert [r.rule_id for r in rules] == ["rule-45", "rule-46"]
    retired = Heuristic(
        rule_id="rule-45",
        summary="baseline",
        applies_when="velocity entry",
        body="Revised baseline evidence.",
        retired=True,
    )
    await write_rule(bot, retired)
    rules, after = await read_catalog(bot)
    assert records["topchicken"] == original
    assert legacy == after
    assert next(r for r in rules if r.rule_id == "rule-45") == retired
    assert next(r for r in rules if r.rule_id == "rule-46").body.endswith(
        "act on the trigger."
    )
    writes = [r for path, r in requests if path.endswith("putRecord")]
    assert len(writes) == 1 and writes[0]["rkey"] == "rule-45"


async def test_recent_interactions_emit_supported_filter_and_recover_text(server):
    url, requests, _ = server
    with Turbopuffer(api_key="fixture", base_url=url, max_retries=0) as client:
        memory = NamespaceMemory.__new__(NamespaceMemory)
        memory.client = client
        rows = await memory.get_recent_interactions()
    assert rows[0]["handle"] == "alice.test"
    assert rows[0]["content"] == "completed exchange"
    assert sum(path.endswith("/query") for path, _ in requests) == 1
