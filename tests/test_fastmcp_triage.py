"""phi's fastmcp watch reads the operator's warehouse through the hub.

The numbers are the operator's maintainer workload, so the rendering has to
say what "maintainer" and "answered" mean and that the triage-reviewed split
is not causal, or a weekly comparison turns into a confident wrong claim.
"""

import inspect
import re

from bot.agent import PhiAgent
from bot.core.fastmcp_triage import Day, Triage, format_triage


def day(d: str, kind: str, opened: int, merged: int, closed: int, open_end: int) -> Day:
    return {
        "day": d,
        "kind": kind,
        "opened": opened,
        "merged": merged,
        "closed_unmerged": closed,
        "open_end": open_end,
        "open_lt_7d": 1,
        "open_7_30d": 2,
        "open_30_90d": 3,
        "open_gt_90d": 4,
    }


PAYLOAD: Triage = {
    "repo": "PrefectHQ/fastmcp",
    "as_of": "2026-11-03",
    "days": [
        day("2026-10-26", "pr", 10, 4, 1, 190),
        day("2026-10-26", "issue", 5, 0, 6, 340),
        day("2026-11-02", "pr", 12, 6, 0, 196),
        day("2026-11-03", "pr", 3, 2, 0, 197),
        day("2026-11-03", "issue", 2, 0, 1, 335),
    ],
    "weeks": [
        {
            "week": "2026-10-19",
            "triage_reviewed": True,
            "prs": 5,
            "merged": 1,
            "still_open": 4,
            "old_enough_7d": 5,
            "responded_7d": 1,
            "old_enough_14d": 3,
            "merged_14d": 0,
            "median_hours_to_first_response": 60.0,
            "median_hours_to_merge": None,
        }
    ],
    "stuck": [
        {
            "number": 4745,
            "title": "Add Authplane auth provider",
            "author": "muralx",
            "created_at": "2026-08-03T19:20:37Z",
            "age_days": 90,
            "triage_reviewed": False,
            "reason": "maintainer quiet",
            "last_maintainer_activity_at": "2026-08-06T13:32:18Z",
            "url": "https://github.com/PrefectHQ/fastmcp/pull/4745",
        }
    ],
}


def test_open_now_uses_the_latest_day_for_each_kind():
    text = format_triage(PAYLOAD)
    assert "PRs: 197 (age <7d 1" in text
    assert "issues: 335" in text


def test_days_roll_up_into_monday_weeks():
    text = format_triage(PAYLOAD)
    assert "week of 2026-10-26: PRs 10 / 4 / 1 / 190; issues 5 / 6 / 340" in text
    assert "week of 2026-11-02: PRs 15 / 8 / 0 / 197; issues 2 / 1 / 335" in text


def test_cohorts_and_stuck_prs_carry_their_meaning():
    text = format_triage(PAYLOAD)
    assert "not causal" in text
    assert "bots don't count" in text
    assert "answered 1/5, merged 0/3 in 14d; median first response 2.5d, median to merge n/a" in text
    assert "issue-link gate" in text
    assert "#4745 90d, maintainer quiet since 2026-08-06: Add Authplane auth provider (muralx)" in text


def test_an_empty_warehouse_says_so():
    empty: Triage = {"repo": "PrefectHQ/fastmcp", "as_of": None, "days": [], "weeks": [], "stuck": []}
    assert "has not synced" in format_triage(empty)


def test_the_watch_reports_privately_and_compares_against_memory():
    task = re.sub(r'"\s*\n\s*"', "", inspect.getsource(PhiAgent.process_fastmcp_watch))
    assert "inspect_fastmcp_triage" in task
    assert "report_operator" in task
    assert "a quiet week needs no message" in task
    assert "search_memory" in task and "save_memory" in task
    assert "stay off the feed" in task


def test_prefect_can_wake_the_watch():
    from bot.main import _TRIGGER_SLOTS

    assert "fastmcp-watch" in _TRIGGER_SLOTS
