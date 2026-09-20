import copy
import json
from pathlib import Path

import httpx
import pytest

from evals.jev import run as runner

PATH = Path(__file__).parents[1] / "evals/jev"


def test_corpus_family_holdout_and_no_label_leakage():
    cases = json.loads((PATH / "cases.json").read_text())
    config = json.loads((PATH / "questions.json").read_text())
    runner.validate(cases, config)
    assert len(cases) == 48
    assert {s: sum(c["split"] == s for c in cases) for s in ["dev", "heldout"]} == {
        "dev": 24,
        "heldout": 24,
    }
    leaked = copy.deepcopy(cases)
    leaked[1]["split"] = "heldout"
    with pytest.raises(AssertionError, match="split leakage"):
        runner.validate(leaked, config)


async def test_budget_rejects_before_network_and_retains_failed_reservation():
    budget = runner.Budget(0.002, 2)
    request = httpx.Request(
        "POST",
        "https://api.typesafe.ai/v1/systemone",
        json={"model": "jev-1.13.0", "state": "x" * 10000},
    )
    await budget.before(request)
    response = httpx.Response(429, request=request, json={"error": "rate limit"})
    await budget.after(response)
    assert budget.reserved > 0
    await budget.before(request)
    with pytest.raises(RuntimeError, match="budget exhausted"):
        await budget.before(request)
    assert budget.requests == 2


async def test_unknown_destination_or_model_never_consumes_budget():
    budget = runner.Budget(5, 10)
    for url, payload in [
        ("https://unexpected.invalid/", {}),
        (
            "https://api.openai.com/v1/responses",
            {"model": "unpriced", "max_output_tokens": 2048},
        ),
        ("https://api.openai.com/v1/responses", {"model": "gpt-5.6-terra"}),
    ]:
        with pytest.raises(RuntimeError):
            await budget.before(httpx.Request("POST", url, json=payload))
    assert budget.requests == 0


def test_uncertainty_and_errors_are_not_counted_as_success_or_false_blocks():
    rows = [
        dict(
            id="uncertain",
            backend="jev",
            split="dev",
            dimension="attention",
            seconds=1,
            expected=True,
            prediction=None,
        ),
        dict(
            id="failed",
            backend="jev",
            split="dev",
            dimension="attention",
            seconds=2,
            expected=False,
            prediction=None,
            error="Timeout",
        ),
    ]
    result = runner.summary(rows)["jev/dev/attention"]
    assert result["abstentions"] == 1
    assert result["errors"] == 1
    assert result["false_allows"] == result["false_blocks"] == []
    with pytest.raises(ValueError):
        runner.decision(float("nan"), {"no": 0.2, "yes": 0.8})


async def test_dollar_ceiling_and_usage_settlement():
    request = httpx.Request(
        "POST",
        "https://api.typesafe.ai/v1/systemone",
        json={"model": "jev-1.13.0", "state": "test"},
    )
    too_small = runner.Budget(0.000001, 10)
    with pytest.raises(RuntimeError, match="budget exhausted"):
        await too_small.before(request)
    assert too_small.requests == 0
    budget = runner.Budget(1, 10)
    await budget.before(request)
    response = httpx.Response(
        200,
        request=request,
        json={
            "model": "jev-1.13.0",
            "usage": {"input_tokens": 100, "output_tokens": 5},
        },
    )
    await budget.after(response)
    assert budget.reserved == pytest.approx(0.0000042)
