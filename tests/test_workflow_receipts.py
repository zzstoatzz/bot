import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from bot.core import operator_reports, workflow_receipts
from bot.tools import workflows
from bot.tools._helpers import PhiDeps


@pytest.fixture
def journal(tmp_path, monkeypatch):
    monkeypatch.setattr(operator_reports, "JOURNAL", tmp_path / "operator.sqlite3")


def test_request_identity_survives_retry_and_rejects_changed_work(journal):
    payload = {
        "request_key": "incident:one",
        "workflow": "investigate",
        "repo": "bot",
        "instructions": "Private task details",
    }
    first = workflow_receipts.reserve(payload, "dm:one")
    assert first["state"] == "unconfirmed"
    retry = workflow_receipts.reserve(payload, "dm:two")
    assert retry == first
    with pytest.raises(ValueError, match="different work"):
        workflow_receipts.reserve(
            {**payload, "instructions": "Deploy instead"}, "dm:two"
        )
    workflow_receipts.confirm("incident:one", "run:one", "investigation")
    assert workflow_receipts.reserve(payload, "dm:two")["flow_run_id"] == "run:one"
    receipt = workflow_receipts.recent("incident:one")[0]
    assert receipt["source_message"] == "dm:one"
    assert "fingerprint" not in receipt
    assert "instructions" not in receipt
    assert b"Private task details" not in operator_reports.JOURNAL.read_bytes()
    assert workflow_receipts.recent("missing") == []


def test_recent_receipts_are_bounded_without_losing_exact_lookup(journal):
    for i in range(12):
        workflow_receipts.reserve(
            {"request_key": str(i), "workflow": "investigate", "repo": "bot"}, ""
        )
    assert len(workflow_receipts.recent()) == 10
    assert workflow_receipts.recent("0")[0]["request_key"] == "0"


async def test_private_status_reads_live_state_without_dispatch(journal, monkeypatch):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append((self.command, self.path))
            body = json.dumps(
                {"state_type": "COMPLETED", "state_name": "Degraded"}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        workflows.settings,
        "prefect_api_url",
        f"http://127.0.0.1:{server.server_port}/api",
    )
    monkeypatch.setattr(workflows.settings, "prefect_api_auth_string", "test:local")
    registered = {}
    workflows.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    workflow_receipts.reserve(
        {"request_key": "one", "repo": "bot", "workflow": "investigate"}, "dm:1"
    )
    workflow_receipts.confirm("one", "run-one", "investigation")
    status = registered["operator_workflow_status"]
    owner = workflows.settings.owner_handle
    try:
        public = await status(SimpleNamespace(deps=PhiDeps(author_handle=owner)))
        assert "error" in public and not calls
        private = await status(
            SimpleNamespace(
                deps=PhiDeps(author_handle=owner, private_message_id="dm:2")
            )
        )
        assert private["requests"][0]["live_status"]["state_name"] == "Degraded"
        assert calls == [("GET", "/api/flow_runs/run-one")]
        monkeypatch.setattr(workflows.settings, "prefect_api_auth_string", None)
        unavailable = await status(
            SimpleNamespace(
                deps=PhiDeps(author_handle=owner, private_message_id="dm:3")
            )
        )
        assert unavailable["requests"][0]["live_status"] == "unavailable"
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
