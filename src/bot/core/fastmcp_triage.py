"""fastmcp triage state from the operator's warehouse, rendered for phi.

my-prefect-server syncs every PrefectHQ/fastmcp issue and PR hourly and models
throughput, contributor wait and stuck PRs (analytics/models/fastmcp/); the hub
serves them at /api/agents/fastmcp-triage. phi reads this for a long-horizon
watch: whether merging keeps pace with intake, whether contributors hear back
sooner or later, and what has been stuck longest.
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import TypedDict

import httpx

from bot.config import settings

logger = logging.getLogger("bot.fastmcp_triage")

HTTP_TIMEOUT = 15.0


class Day(TypedDict):
    day: str
    kind: str
    opened: int
    merged: int
    closed_unmerged: int
    open_end: int
    open_lt_7d: int
    open_7_30d: int
    open_30_90d: int
    open_gt_90d: int


class Week(TypedDict):
    week: str
    triage_reviewed: bool
    prs: int
    merged: int
    still_open: int
    old_enough_7d: int
    responded_7d: int
    old_enough_14d: int
    merged_14d: int
    median_hours_to_first_response: float | None
    median_hours_to_merge: float | None


class StuckPr(TypedDict):
    number: int
    title: str
    author: str
    created_at: str
    age_days: int
    triage_reviewed: bool
    reason: str
    last_maintainer_activity_at: str | None
    url: str


class Triage(TypedDict):
    repo: str
    as_of: str | None
    days: list[Day]
    weeks: list[Week]
    stuck: list[StuckPr]


async def fetch_triage(weeks: int, stuck_limit: int) -> Triage:
    params = {"days": weeks * 7, "weeks": weeks, "stuck_limit": stuck_limit}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(settings.fastmcp_triage_url, params=params)
        response.raise_for_status()
        return response.json()


def _hours(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value / 24:.1f}d" if value >= 48 else f"{value:.0f}h"


def _share(part: int, whole: int) -> str:
    return f"{part}/{whole}" if whole else "n/a"


def format_triage(data: Triage) -> str:
    days = data["days"]
    if not days:
        return "no fastmcp triage data yet (the warehouse has not synced)."
    latest = {d["kind"]: d for d in days if d["day"] == days[-1]["day"]}
    lines = [
        f"PrefectHQ/fastmcp triage as of {data['as_of']} (days in America/Chicago).",
        "maintainer = a human OWNER/MEMBER/COLLABORATOR other than the author; bots don't count.",
        "",
        "open now:",
    ]
    for kind, label in (("issue", "issues"), ("pr", "PRs")):
        d = latest.get(kind)
        if d:
            lines.append(
                f"  {label}: {d['open_end']} (age <7d {d['open_lt_7d']}, 7-30d {d['open_7_30d']}, "
                f"30-90d {d['open_30_90d']}, >90d {d['open_gt_90d']})"
            )

    by_week: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    for d in days:
        monday = date.fromisoformat(d["day"])
        monday -= timedelta(days=monday.weekday())
        bucket = by_week[monday.isoformat()][d["kind"]]
        for key in ("opened", "merged", "closed_unmerged"):
            bucket[key] = bucket.get(key, 0) + d[key]
        bucket["open_end"] = d["open_end"]
    lines += ["", "weekly flow (opened / merged / closed unmerged / open at week end):"]
    for week in sorted(by_week):
        parts = []
        for kind, label in (("pr", "PRs"), ("issue", "issues")):
            b = by_week[week].get(kind)
            if b:
                merged = f"{b['merged']} / " if kind == "pr" else ""
                parts.append(
                    f"{label} {b['opened']} / {merged}{b['closed_unmerged']} / {b['open_end']}"
                )
        lines.append(f"  week of {week}: " + "; ".join(parts))

    lines += [
        "",
        "contributor PRs by the week they were opened, triage-reviewed vs not",
        "(answered = first maintainer comment, review or merge within 7 days; merged = merged",
        "within 14 days; each only counts PRs old enough to have had the chance. closures are",
        "left out: automation such as the issue-link gate closes many contributor PRs).",
        "the triage reviewer picks which PRs it reviews, so the split is not causal.",
    ]
    for w in data["weeks"]:
        tag = "reviewed" if w["triage_reviewed"] else "not reviewed"
        lines.append(
            f"  {w['week']} {tag}: {w['prs']} PRs, {w['merged']} merged, {w['still_open']} open; "
            f"answered {_share(w['responded_7d'], w['old_enough_7d'])}, "
            f"merged {_share(w['merged_14d'], w['old_enough_14d'])} in 14d; "
            f"median first response {_hours(w['median_hours_to_first_response'])}, "
            f"median to merge {_hours(w['median_hours_to_merge'])}"
        )

    stuck = data["stuck"]
    lines += ["", f"stuck contributor PRs, oldest first ({len(stuck)} shown):"]
    if not stuck:
        lines.append("  none")
    for s in stuck:
        detail = (
            "no maintainer response"
            if s["reason"] == "no maintainer response"
            else f"maintainer quiet since {(s['last_maintainer_activity_at'] or '')[:10]}"
        )
        reviewed = ", triage-reviewed" if s["triage_reviewed"] else ""
        lines.append(f"  #{s['number']} {s['age_days']}d, {detail}{reviewed}: {s['title']} ({s['author']})")
    return "\n".join(lines)
