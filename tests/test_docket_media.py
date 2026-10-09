import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from pydantic_ai import Agent, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from bot.core import media
from bot.tools import media as media_tool

DOCKET = "io.zzstoatzz.phi.docket"
URI = f"at://did:plc:65sucjiel52gefhcdcypynsr/{DOCKET}/self"


@pytest.mark.parametrize(
    ("payload", "record_type", "expected", "fetches_blob"),
    [
        (
            b'{"candidates": [{"rationale": "read the source"}]}',
            DOCKET,
            "read the source",
            True,
        ),
        (b"not JSON", DOCKET, "JSONDecodeError", True),
        (
            b" " * (media_tool.MAX_TEXT_BYTES + 1),
            DOCKET,
            "exceeds the read limit",
            True,
        ),
        (b"binary", "example.file", "no allowed text/image blobs", False),
    ],
)
async def test_docket_reader_over_http(
    monkeypatch, payload, record_type, expected, fetches_blob
):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            requests.append(path)
            data = payload
            if path.endswith("getRecord"):
                data = json.dumps(
                    {
                        "uri": URI,
                        "value": {
                            "$type": record_type,
                            "blob": {
                                "ref": {"$link": "bafyblob"},
                                "mimeType": "application/octet-stream",
                            },
                        },
                    }
                ).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def resolve_pds(did):
        return f"http://127.0.0.1:{server.server_port}"

    monkeypatch.setattr(media, "_resolve_pds", resolve_pds)
    agent = Agent("test")
    media_tool.register(agent)
    tool = agent._function_toolset.tools["inspect_record_media"].function
    try:
        result = await tool(
            RunContext(deps=None, model=TestModel(), usage=RunUsage()), URI
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert expected in str(result)
    assert ("/xrpc/com.atproto.sync.getBlob" in requests) is fetches_blob


def test_docket_binary_exception_does_not_include_other_fields():
    blob = {"ref": {"$link": "bafyblob"}, "mimeType": "application/octet-stream"}
    refs = media.find_allowed_blobs({"$type": DOCKET, "blob": blob, "attachment": blob})
    assert [(ref.path, ref.mime_type) for ref in refs] == [("blob", "application/json")]
