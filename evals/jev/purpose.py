"""Evaluate independent communication properties without a publication verdict."""

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from evals.jev.run import Budget, decision, fingerprint

ROOT = Path(__file__).parent


def load_cases():
    cases = json.loads((ROOT / "purpose-cases.json").read_text())
    config = json.loads((ROOT / "purpose.json").read_text())
    families = {}
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert families.setdefault(case["family"], case["split"]) == case["split"]
        assert set(case["expected"]) == set(config["questions"])
        assert set(case["state"]) == {"context", "action"}
        assert all(type(x) is bool for x in case["expected"].values())
    return cases, config


async def run(args):
    cases, config = load_cases()
    selected = [c for c in cases if c["split"] == args.split]
    budget = Budget(0.25, len(selected) * args.repeats)
    manifest = dict(
        started_at=datetime.now(UTC).isoformat(),
        config=config,
        corpus_sha256=fingerprint(cases),
        config_sha256=fingerprint(config),
        case_ids=[c["id"] for c in selected],
        repeats=args.repeats,
        ceiling_usd=0.25,
        concurrency=1,
        retries=0,
        labels="agent-reviewed semantic properties; no final permission verdict",
    )
    if not args.execute:
        print(json.dumps(manifest, indent=2))
        return
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise SystemExit("TYPESAFE_API_KEY required")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps({"manifest": manifest}) + "\n")
    rows = []
    async with httpx.AsyncClient(
        timeout=30, event_hooks={"request": [budget.before], "response": [budget.after]}
    ) as client:
        for repeat in range(args.repeats):
            for case in selected:
                row = dict(
                    id=case["id"],
                    split=case["split"],
                    repeat=repeat,
                    expected=case["expected"],
                )
                start = time.perf_counter()
                try:
                    response = await client.post(
                        "https://api.typesafe.ai/v1/systemone",
                        headers={"Authorization": f"Bearer {key}"},
                        json={
                            "model": config["model"],
                            "state": case["state"],
                            "questions": config["questions"],
                        },
                    )
                    response.raise_for_status()
                    row["answers"] = response.json()["answers"]
                    row["predictions"] = {
                        k: decision(float(v["noul"]), config["thresholds"])
                        for k, v in row["answers"].items()
                    }
                    if set(row["predictions"]) != set(config["questions"]):
                        raise ValueError("Incomplete response")
                except Exception as exc:
                    row["error"] = type(exc).__name__
                row["seconds"] = time.perf_counter() - start
                rows.append(row)
                with output.open("a") as stream:
                    stream.write(json.dumps(row) + "\n")
                if "error" in row:
                    break
            if "error" in rows[-1]:
                break
    summary = {}
    for question in config["questions"]:
        labeled = [r for r in rows if "error" not in r]
        summary[question] = {
            "n": len(labeled),
            "correct": sum(
                r["predictions"][question] == r["expected"][question] for r in labeled
            ),
            "wrong": [
                r["id"]
                for r in labeled
                if r["predictions"][question] is not None
                and r["predictions"][question] != r["expected"][question]
            ],
            "abstain": [r["id"] for r in labeled if r["predictions"][question] is None],
        }
    complete = len(rows) == len(selected) * args.repeats and not any(
        "error" in r for r in rows
    )
    result = dict(
        summary=summary,
        complete=complete,
        spent_or_reserved_usd=budget.reserved,
        calls=budget.calls,
    )
    with output.open("a") as stream:
        stream.write(json.dumps(result) + "\n")
    print(json.dumps(result, indent=2))
    if not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--split", choices=["dev", "heldout"], default="dev")
    parser.add_argument("--repeats", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))
