import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TypedDict

import pytest
from pydantic import SecretStr

from bot.core.chicken_strategy import (
    Heuristic,
    legacy_rules,
    lookup,
    select_rules,
    selection_state,
)
from bot.services import typesafe


class ResponseState(TypedDict):
    status: int
    scores: dict[str, float]


@pytest.fixture
def endpoint():
    requests = []
    response: ResponseState = {
        "status": 200,
        "scores": {"rule-45": 0.9, "rule-46": 0.1},
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(
                json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            )
            payload = {
                "model": "jev-1.13.0",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "answers": {
                    k: {"type": "noul", "noul": v}
                    for k, v in response["scores"].items()
                },
            }
            body = json.dumps(payload).encode()
            self.send_response(response["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", requests, response
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def rules():
    return [
        Heuristic(
            rule_id="rule-45",
            summary="check earlier baseline",
            applies_when="entering on velocity agreement",
            body="Read an earlier checkpoint before entry.",
        ),
        Heuristic(
            rule_id="rule-46",
            summary="exit before clock",
            applies_when="exit trigger met",
            body="Act on the exit condition.",
        ),
    ]


def test_legacy_rules_preserve_body_without_recaps_or_invented_rules():
    text = "Recap we must not inject.\n\nRULE 45 (baseline): inspect earlier evidence.\n\nKeep this second paragraph.\n\nRULE 46 (exit): act on the condition.\n\nSeason state: yesterday's figures.\n\nRules 1-44 unchanged."
    rules = legacy_rules(text)
    assert [r.rule_id for r in rules] == ["rule-45", "rule-46"]
    assert "second paragraph" in rules[0].body
    assert "Season state" not in rules[1].body
    assert "not available" in lookup(rules, text, "rule-1")
    assert lookup(rules, text, "legacy") == text


@pytest.mark.parametrize(
    "mode", ["selection", "none", "http-error", "missing-answer", "retired"]
)
async def test_real_sdk_batch_and_failure_contract(endpoint, monkeypatch, rules, mode):
    url, requests, response = endpoint
    monkeypatch.setattr(
        typesafe.settings, "typesafe_api_key", SecretStr("local-fixture")
    )
    monkeypatch.setattr(typesafe.settings, "typesafe_base_url", url)
    await typesafe.close_client()
    if mode == "none":
        response["scores"] = {"rule-45": 0.1, "rule-46": 0.1}
    elif mode == "http-error":
        response["status"] = 503
    elif mode == "missing-answer":
        response["scores"] = {"rule-45": 0.9}
    elif mode == "retired":
        rules[1].retired = True
        response["scores"] = {"rule-45": 0.9}
    try:
        out = await select_rules(
            rules, {"round": {"id": "today"}, "wallet": {"positions": []}}
        )
        assert len(requests) == 1
        assert set(requests[0]["questions"]) == (
            {"rule-45"} if mode == "retired" else {"rule-45", "rule-46"}
        )
        if mode in {"http-error", "missing-answer"}:
            assert "selection unavailable" in out
            assert rules[0].body not in out
        elif mode == "none":
            assert "No rules matched" in out
        else:
            assert rules[0].body in out
            assert rules[1].body not in out
    finally:
        await typesafe.close_client()


async def test_incomplete_market_does_not_call_provider(endpoint, monkeypatch, rules):
    url, requests, _ = endpoint
    monkeypatch.setattr(
        typesafe.settings, "typesafe_api_key", SecretStr("local-fixture")
    )
    monkeypatch.setattr(typesafe.settings, "typesafe_base_url", url)
    out = await select_rules(rules, {"round": {"id": "today"}})
    assert "incomplete" in out
    assert not requests


def test_selection_uses_current_evidence_and_keeps_held_and_requested_tail():
    contenders = [
        {
            "did": f"c{i}",
            "handle": f"h{i}",
            "p": (100 - i) / 100,
            "likes": i,
            "post_text": "not needed",
            "avatar": "large",
            "deltas": {"1h": {"likes": 100 - i}},
        }
        for i in range(236)
    ]
    state = selection_state(
        {
            "round": {"contenders": contenders},
            "wallet": {
                "positions": [{"contender_did": "c234"}],
                "trades": [{"old": "narrative"}],
            },
            "requested_handle": "@h235",
        }
    )
    selected = state["round"]["contenders"]
    assert {"c234", "c235"} <= {c["did"] for c in selected}
    assert len(selected) == 14
    assert state["round"]["total_contenders"] == 236
    assert "trades" not in state["wallet"]
    assert all("post_text" not in c and "avatar" not in c for c in selected)
    assert "omitted" in state["scope"]
