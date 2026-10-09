import json
from pathlib import Path

import pytest

from bot.core.policy import check_action

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "operator_dms.json").read_text()
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_private_delivery(case):
    verdict = await check_action(
        action=case["text"], provenance=case["context"], tool=case["tool"]
    )
    assert (verdict["verdict"] == "allow") == case["allowed"], verdict
