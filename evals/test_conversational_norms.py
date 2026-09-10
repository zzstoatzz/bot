"""Direct production-judge regressions; no publication or bot execution."""

import json
from pathlib import Path

import pytest

from bot.core import etiquette, policy

CASES = json.loads(
    (Path(__file__).parent / "fixtures/conversational_norms.json").read_text()
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
async def test_conversational_norms(case, tmp_path, monkeypatch):
    monkeypatch.setattr(etiquette, "JOURNAL", tmp_path / "attempts.sqlite3")
    verdict = await policy.check_action(case["action"], case["provenance"], tool="post")
    assert verdict["verdict"] == case["expected"], verdict
    if "policy" in case:
        assert verdict["policy"] == case["policy"], verdict
