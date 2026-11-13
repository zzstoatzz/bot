"""The export review separates disclosing a private exchange from acting on it."""

import pytest

from bot.core import export_guard
from bot.core.export_guard import Permissioned

OPERATOR = "did:plc:operator"


def conversation(*operator_lines: str) -> Permissioned:
    text = "\n".join(f"operator: {line}" for line in operator_lines)
    return Permissioned("private operator conversation", text, frozenset({OPERATOR}))


CASES = [
    (
        "a confidence restated in a public record",
        conversation(
            "between us, i'm interviewing at another company next week. "
            "keep the infra reports short until then, i'll be distracted."
        ),
        "update_goal_progress",
        {"progress": "Nate is interviewing elsewhere next week, so reports stay short."},
        True,
    ),
    (
        "a paraphrase with no names",
        conversation("the tunnel password got leaked in a screenshot, rotating tonight."),
        "write_self",
        {"text": "My operator had a credential exposed in an image and is replacing it."},
        True,
    ),
    (
        "revealing that the private exchange happened",
        conversation("stop double replying on the devlog thread."),
        "pdsx create_record",
        {
            "collection": "io.zzstoatzz.phi.note",
            "record": {"text": "Got a DM from Nate telling me off about double replies."},
        },
        True,
    ),
    (
        "the write the operator asked for",
        conversation(
            "update your goal progress to say the float probe is done and "
            "the records can't be stored from your pds."
        ),
        "update_goal_progress",
        {"progress": "Float probe is done. The records can't be stored from my PDS."},
        False,
    ),
    (
        "an unrelated write in the same run",
        conversation("the prefect tunnel was down this morning, it's back."),
        "update_goal_progress",
        {"progress": "12 likes on my own posts so far this month, from the public counts."},
        False,
    ),
    (
        "acting on a request without restating it",
        conversation("follow @astrra.space, she's good."),
        "follow_user",
        {"handle": "astrra.space"},
        False,
    ),
]


@pytest.mark.parametrize(
    "item,tool,args,discloses", [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
async def test_export_review(item, tool, args, discloses):
    refusal = await export_guard.review(tool, args, [item])
    assert (refusal is not None) is discloses, refusal
