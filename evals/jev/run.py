"""Bounded, opt-in real-provider experiment; run from the repository root."""

import argparse
import asyncio
import hashlib
import json
import logging
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from bot.core import etiquette, operator_reports, policy

ROOT = Path(__file__).parent
RATES = {"jev": (0.042, 0.0), "baseline": (2.0, 12.0)}
MAX_OUTPUT = 2048


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate(cases, config):
    ids, families = set(), {}
    for case in cases:
        assert case["id"] not in ids, "duplicate case"
        ids.add(case["id"])
        assert case["split"] in {"dev", "heldout"}
        assert case["dimension"] in config["questions"]
        assert type(case["expected"]) is bool
        assert case["source"] and case["rationale"]
        assert set(case["state"]) == {"action", "provenance", "prior_coverage"}
        assert families.setdefault(case["family"], case["split"]) == case["split"], (
            "split leakage"
        )
    for thresholds in config["thresholds"].values():
        assert 0 <= thresholds["no"] < thresholds["yes"] <= 1


def decision(probability, thresholds):
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("invalid probability")
    if probability >= thresholds["yes"]:
        return True
    if probability <= thresholds["no"]:
        return False
    return None


class Budget:
    def __init__(self, dollars, requests):
        self.limit = dollars
        self.max_requests = requests
        self.reserved = 0.0
        self.requests = 0
        self.calls = []

    async def before(self, request):
        backend = "jev" if request.url.host == "api.typesafe.ai" else "baseline"
        if (request.url.host, request.url.path) not in {
            ("api.typesafe.ai", "/v1/systemone"),
            ("api.openai.com", "/v1/responses"),
        }:
            raise RuntimeError("unexpected network destination")
        payload = json.loads(request.content)
        if backend == "baseline" and payload.get("max_output_tokens") != MAX_OUTPUT:
            raise RuntimeError("missing output cap")
        if backend == "baseline" and payload.get("model") != "gpt-5.6-terra":
            raise RuntimeError("unpriced baseline model")
        if backend == "jev" and payload.get("model") != "jev-1.13.0":
            raise RuntimeError("unpriced jev model")
        tokens = len(request.content) + 8192
        rates = RATES[backend]
        reserve = (tokens * rates[0] + MAX_OUTPUT * rates[1]) / 1e6
        if self.requests >= self.max_requests or self.reserved + reserve > self.limit:
            raise RuntimeError("budget exhausted before request")
        self.requests += 1
        self.reserved += reserve
        call = {
            "backend": backend,
            "reserved_usd": reserve,
            "request_sha256": fingerprint(payload),
        }
        self.calls.append(call)
        request.extensions["eval_call"] = call

    async def after(self, response):
        await response.aread()
        call = response.request.extensions["eval_call"]
        call["status"] = response.status_code
        if response.is_success:
            data = response.json()
            usage = data.get("usage", {})
            if "input_tokens" in usage and "output_tokens" in usage:
                call["usage"] = usage
                call["model"] = data.get("model")
                rates = RATES[call["backend"]]
                cost = (
                    usage["input_tokens"] * rates[0] + usage["output_tokens"] * rates[1]
                ) / 1e6
                call["estimated_usd"] = cost
                if cost > call["reserved_usd"]:
                    raise RuntimeError("token reservation exceeded; stop evaluation")
                self.reserved += cost - call["reserved_usd"]


def summary(rows):
    groups = {}
    for row in rows:
        key = f"{row['backend']}/{row['split']}/{row['dimension']}"
        groups.setdefault(key, []).append(row)
    report = {}
    for key, group in groups.items():
        latencies = sorted(r["seconds"] for r in group)
        report[key] = {
            "n": len(group),
            "errors": sum("error" in r for r in group),
            "abstentions": sum(
                r.get("prediction") is None and "error" not in r for r in group
            ),
            "false_allows": [
                r["id"]
                for r in group
                if r.get("prediction") is True and not r["expected"]
            ],
            "false_blocks": [
                r["id"] for r in group if r.get("prediction") is False and r["expected"]
            ],
            "p50_s": latencies[(len(latencies) - 1) // 2],
            "p95_s": latencies[math.ceil(len(latencies) * 0.95) - 1],
        }
    return report


async def evaluate(args):
    cases = json.loads((ROOT / "cases.json").read_text())
    config = json.loads((ROOT / "questions.json").read_text())
    validate(cases, config)
    selected = [c for c in cases if c["split"] == args.split]
    if args.case_id:
        selected = [c for c in selected if c["id"] in args.case_id]
        if {c["id"] for c in selected} != set(args.case_id):
            raise SystemExit("Unknown case ID or wrong split")
    selected = selected[: args.limit]
    manifest = {
        "started_at": datetime.now(UTC).isoformat(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256(Path("uv.lock").read_bytes()).hexdigest(),
        "corpus_sha256": fingerprint(cases),
        "config_sha256": fingerprint(config),
        "config": config,
        "split": args.split,
        "case_ids": [c["id"] for c in selected],
        "repeats": args.repeats,
        "ceiling_usd": args.budget,
        "rates_per_million": RATES,
        "output_cap": MAX_OUTPUT,
        "concurrency": 1,
        "automatic_retries": False,
        "cost_note": "List-price estimate, cached input charged at full price; failed requests retain reservation. Input reservation is serialized UTF-8 bytes + 8192 tokens, checked against reported usage.",
        "labels": "agent-authored, policy-grounded; not independently human-reviewed",
    }
    if not args.execute:
        print(json.dumps(manifest, indent=2))
        return
    load_dotenv(override=False)
    if not os.environ.get("TYPESAFE_API_KEY") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Both provider keys must be supplied; no requests made")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps({"manifest": manifest}) + "\n")
    budget = Budget(args.budget, len(selected) * args.repeats * 2)
    rows = []
    async with httpx.AsyncClient(
        timeout=45, event_hooks={"request": [budget.before], "response": [budget.after]}
    ) as http:
        client = AsyncOpenAI(
            api_key=os.environ["OPENAI_API_KEY"], http_client=http, max_retries=0
        )
        model = OpenAIResponsesModel(
            "gpt-5.6-terra",
            provider=OpenAIProvider(openai_client=client),
            settings={"max_tokens": MAX_OUTPUT},
        )
        judge = policy._get_judge()
        judge._max_result_retries = 0
        manifest["policy_sha256"] = fingerprint(
            {"policies": policy.POLICIES, "system": judge._system_prompts}
        )
        logging.getLogger("bot.policy").setLevel(logging.CRITICAL)
        with output.open("a") as stream:
            stream.write(
                json.dumps({"baseline_policy_sha256": manifest["policy_sha256"]}) + "\n"
            )
        for repeat in range(args.repeats):
            for case in selected:
                for backend in ("jev", "baseline"):
                    row = {
                        k: case[k]
                        for k in ("id", "split", "dimension", "expected", "critical")
                    }
                    row.update(backend=backend, repeat=repeat)
                    start = time.perf_counter()
                    call_start = len(budget.calls)
                    try:
                        if backend == "jev":
                            response = await http.post(
                                "https://api.typesafe.ai/v1/systemone",
                                headers={
                                    "Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"
                                },
                                json={
                                    "model": config["model"],
                                    "state": case["state"],
                                    "questions": config["questions"],
                                },
                            )
                            response.raise_for_status()
                            data = response.json()
                            row["answers"] = data["answers"]
                            probability = float(
                                data["answers"][case["dimension"]]["noul"]
                            )
                            row["probability"] = probability
                            row["prediction"] = decision(
                                probability, config["thresholds"][case["dimension"]]
                            )
                        else:
                            with (
                                judge.override(model=model),
                                patch.object(etiquette, "pending", return_value=None),
                                patch.object(
                                    etiquette, "record", return_value="offline-eval"
                                ),
                                patch.object(
                                    operator_reports,
                                    "delivery_context",
                                    new=AsyncMock(
                                        return_value="Offline case; no unsolicited public incident escalation is eligible."
                                    ),
                                ),
                            ):
                                verdict = await policy.check_action(
                                    action=case["state"]["action"],
                                    provenance=case["state"]["provenance"],
                                    prior_coverage=case["state"]["prior_coverage"],
                                    tool=case["tool"],
                                )
                            row["verdict"] = verdict
                            row["prediction"] = verdict["verdict"] != "block"
                        row["correct"] = row["prediction"] == row["expected"]
                    except Exception as exc:
                        row["error"] = type(exc).__name__
                        row["prediction"] = None
                    row["seconds"] = time.perf_counter() - start
                    row["calls"] = budget.calls[call_start:]
                    rows.append(row)
                    with output.open("a") as stream:
                        stream.write(json.dumps(row) + "\n")
                    print(
                        row["id"],
                        backend,
                        row.get("prediction"),
                        row.get("error", ""),
                        flush=True,
                    )
                    if "error" in row:
                        print(
                            "Stopped on provider/harness error; no automatic retry.",
                            flush=True,
                        )
                        break
                if "error" in rows[-1]:
                    break
            if "error" in rows[-1]:
                break
    report = {
        "groups": summary(rows),
        "requests": budget.requests,
        "spent_or_reserved_usd": budget.reserved,
        "complete": len(rows) == len(selected) * args.repeats * 2
        and all("error" not in r for r in rows),
    }
    with output.open("a") as stream:
        stream.write(json.dumps({"summary": report}) + "\n")
    print(json.dumps(report, indent=2))
    if not report["complete"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "heldout"], default="dev")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--budget", type=float, default=5.0)
    parser.add_argument("--output", default="scratch/jev/results.jsonl")
    args = parser.parse_args()
    if (
        not 1 <= args.limit <= 24
        or not 1 <= args.repeats <= 3
        or not 0 < args.budget <= 5
    ):
        parser.error("limit 1–24, repeats 1–3, budget >0 and <=5 required")
    asyncio.run(evaluate(args))


if __name__ == "__main__":
    main()
