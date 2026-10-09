import json
from pathlib import Path

import pytest

from bot.core.policy import POLICIES, _get_judge

CASES = json.loads((Path(__file__).parent / "fixtures" / "phrasing.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_live_judge_checks_phrasing_without_rejecting_useful_language(case):
    prompt = "\n".join(
        [
            f"tool: {case['tool']}",
            "policies:",
            *(f"- {slug}: {text}" for slug, text in POLICIES.items()),
            f"proposed action: {case['text']}",
            f"provenance: {case['context']}",
            "application-verified contact targets: []",
            "operator identities: @zzstoatzz.io, @zzstoatzzdevlog.bsky.social",
        ]
    )
    result = await _get_judge().run(prompt)
    verdict = result.output
    assert (verdict["verdict"] == "allow") == case["allowed"], verdict
    if not case["allowed"]:
        assert verdict["verdict"] == "block", verdict
        assert verdict["policy"] == "public-etiquette", verdict
        assert verdict.get("reason"), verdict
