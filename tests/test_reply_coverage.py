import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from bot.core import reply_coverage as coverage

DID = "did:plc:phi"
PARENT = "at://did:plc:operator/app.bsky.feed.post/question"
REPLY = f"at://{DID}/app.bsky.feed.post/answer"


@pytest.mark.parametrize(
    "mode", ["complete", "missing", "wrong-parent", "outage", "cursor-loop"]
)
async def test_exact_interaction_lookup_over_http(monkeypatch, mode):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            request = urlsplit(self.path)
            params = parse_qs(request.query)
            calls.append((request.path, params))
            if mode == "outage":
                self.send_error(503)
                return
            if request.path.endswith("getBacklinks"):
                assert params["subject"] == [PARENT]
                assert params["did"] == [DID]
                assert params["source"] == ["app.bsky.feed.post:reply.parent.uri"]
                data = {
                    "records": []
                    if "cursor" not in params
                    else [
                        {
                            "did": DID,
                            "collection": "app.bsky.feed.post",
                            "rkey": "answer",
                        }
                    ],
                    "cursor": "next"
                    if mode == "cursor-loop" or "cursor" not in params
                    else None,
                }
            else:
                assert params["uris"] == [REPLY]
                data = {
                    "posts": []
                    if mode == "missing"
                    else [
                        {
                            "uri": REPLY,
                            "author": {"did": DID},
                            "record": {
                                "text": "Already answered",
                                "createdAt": "2026-09-19T21:05:59Z",
                                "reply": {
                                    "parent": {
                                        "uri": "other"
                                        if mode == "wrong-parent"
                                        else PARENT
                                    }
                                },
                            },
                        }
                    ]
                }
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(coverage, "CONSTELLATION", url)
    monkeypatch.setattr(coverage, "APPVIEW", url)
    try:
        async with httpx.AsyncClient() as http:
            if mode in {"wrong-parent", "outage"}:
                with pytest.raises((ValueError, httpx.HTTPStatusError)):
                    await coverage.read_replies(http, PARENT, DID)
                return
            result = await coverage.read_replies(http, PARENT, DID)
        assert result["indexed_reply_uris"] == [REPLY]
        assert result["unhydrated"] == ([REPLY] if mode == "missing" else [])
        assert result["index_pages_exhausted"] == (mode != "cursor-loop")
        assert len(calls) == 3
        if mode != "missing":
            assert result["replies"][0]["text"] == "Already answered"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
