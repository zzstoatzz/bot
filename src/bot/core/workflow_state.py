"""[WORKFLOW STATE] — synthesized current state of the operator's workflow automation.

Phi has access to raw flow run history via MCP, but reasoning about
temporal currency from a 30-row table was inconsistent — sometimes she
correctly identified resolved chains, sometimes she pattern-matched on
"long failure history = persistent problem" and re-flagged things that
had self-resolved hours ago.

This pre-fetches recent flow runs + deployments, runs them through a
small synth agent anchored by [NOW], and returns one line per
deployment: its current health, grounded in timestamps relative to now.
The synth does the temporal aggregation so phi doesn't have to.

Mirrors the [RELEVANT MEMORIES] pattern: raw retrieval → small synth →
coherent block. Phi can still call the prefect_* tools for detail; this
gives her a correct starting picture.

The naming is deliberately abstract — the workflow tool happens to be
prefect today; tomorrow it could be anything else with the same surface.
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic_ai import Agent

from bot.config import settings

logger = logging.getLogger("bot.workflow_state")

_TTL_SECONDS = 300  # 5min
_cache: dict[str, Any] = {"text": "", "fetched_at": 0.0}

_synth_agent: Agent | None = None


def _get_synth_agent() -> Agent:
    global _synth_agent
    if _synth_agent is None:
        _synth_agent = Agent[None, str](
            name="phi-workflow-synth",
            model=settings.extraction_model,
            system_prompt=(
                "You're synthesizing the current state of the operator's "
                "workflow automation for phi to read. You'll see [NOW] and "
                "the recent flow runs grouped by deployment.\n\n"
                "For each deployment with activity in the data, output one "
                "line:\n"
                "  - <deployment-name>: <healthy|broken|stuck|degraded>. "
                "<one short clause grounding it in actual timestamps vs NOW>\n\n"
                "Definitions, anchored by NOW:\n"
                "- healthy: the most recent run for this deployment "
                "completed successfully. earlier failures, if any, are "
                "historical.\n"
                "- broken: the most recent run failed AND no later run has "
                "succeeded. currently unresolved.\n"
                "- stuck: a run has been Pending/Submitting/Running far "
                "longer than the deployment's typical duration.\n"
                "- degraded: a meaningful fraction of recent runs are "
                "failing while others succeed.\n\n"
                "Resolved incidents are not current state. Don't surface "
                "them unless they happened in the last hour. When you cite "
                'time, cite it relative to NOW ("resolved 30h ago", '
                '"failing for 5d") rather than absolute dates.\n\n'
                "Plain ASCII, lowercase, terse. No headers, no preamble — "
                "just the per-deployment lines."
            ),
            output_type=str,
        )
    agent = _synth_agent
    assert agent is not None
    return agent


def _basic_auth() -> tuple[str, str] | None:
    """Parse PREFECT_API_AUTH_STRING into (user, pass) for httpx basic auth."""
    raw = settings.prefect_api_auth_string
    if not raw or ":" not in raw:
        return None
    user, _, pwd = raw.partition(":")
    return user, pwd


async def _fetch_raw() -> dict[str, Any] | None:
    """Pull recent flow runs + deployments from the prefect REST API."""
    auth = _basic_auth()
    if not auth:
        return None
    base = settings.prefect_api_url.rstrip("/")

    # Stuck candidates: PENDING/RUNNING runs whose expected start was
    # more than an hour ago. They may have been started days ago and
    # would fall out of the recent-activity window. The 1h floor avoids
    # flagging legitimately-running short jobs.
    stuck_cutoff = (
        (datetime.now(UTC) - timedelta(hours=1))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    async with httpx.AsyncClient(timeout=15, auth=auth) as client:
        try:
            # Past-activity states only — SCHEDULED rows are future-pending
            # placeholders that drown out the actual signal.
            runs_resp = await client.post(
                f"{base}/flow_runs/filter",
                json={
                    "limit": 100,
                    "sort": "START_TIME_DESC",
                    "flow_runs": {
                        "state": {
                            "type": {
                                "any_": [
                                    "COMPLETED",
                                    "FAILED",
                                    "CRASHED",
                                    "RUNNING",
                                    "CANCELLED",
                                ]
                            }
                        }
                    },
                },
            )
            runs_resp.raise_for_status()
            runs = runs_resp.json()
        except Exception as e:
            logger.debug(f"workflow_state: failed to fetch runs: {e}")
            return None

        try:
            stuck_resp = await client.post(
                f"{base}/flow_runs/filter",
                json={
                    "limit": 20,
                    "sort": "START_TIME_ASC",
                    "flow_runs": {
                        "state": {"type": {"any_": ["PENDING", "RUNNING"]}},
                        "expected_start_time": {"before_": stuck_cutoff},
                    },
                },
            )
            stuck_resp.raise_for_status()
            stuck = stuck_resp.json()
        except Exception as e:
            logger.debug(f"workflow_state: failed to fetch stuck candidates: {e}")
            stuck = []

        try:
            deps_resp = await client.post(
                f"{base}/deployments/filter",
                json={"limit": 100},
            )
            deps_resp.raise_for_status()
            deployments = deps_resp.json()
        except Exception as e:
            logger.debug(f"workflow_state: failed to fetch deployments: {e}")
            deployments = []

    return {"runs": runs, "stuck": stuck, "deployments": deployments}


async def get_workflow_state_block() -> str:
    """Compose [WORKFLOW STATE] — per-deployment health, anchored by NOW."""
    now = time.time()
    if _cache["text"] and now - _cache["fetched_at"] < _TTL_SECONDS:
        return _cache["text"]

    raw = await _fetch_raw()
    if not raw:
        return ""

    runs = raw.get("runs") or []
    stuck = raw.get("stuck") or []
    deployments = raw.get("deployments") or []
    if not runs and not stuck:
        return ""

    dep_names = {d["id"]: d.get("name", "?") for d in deployments}
    now_iso = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    def _line(r: dict) -> str:
        dep = dep_names.get(r.get("deployment_id"), "<no-deployment>")
        state_type = r.get("state_type") or r.get("state", {}).get("type", "?")
        state_name = r.get("state_name") or r.get("state", {}).get("name", "")
        state = f"{state_type}/{state_name}" if state_name else state_type
        name = r.get("name", "?")
        start = r.get("start_time") or r.get("expected_start_time", "")
        end = r.get("end_time", "")
        return f"- {dep} | run={name} | state={state} | start={start} | end={end}"

    sections = [f"[NOW]: {now_iso}"]
    if runs:
        sections.append(
            "recent flow runs (most recent first, max 100):\n"
            + "\n".join(_line(r) for r in runs)
        )
    if stuck:
        sections.append(
            "stuck candidates (PENDING/RUNNING with expected_start more than now):\n"
            + "\n".join(_line(r) for r in stuck)
        )
    payload = "\n\n".join(sections)

    try:
        result = await _get_synth_agent().run(payload)
        text = (result.output or "").strip()
    except Exception as e:
        logger.warning(f"workflow state synth failed: {e}")
        return ""

    if not text:
        return ""

    block = (
        "[WORKFLOW STATE — synthesized current health of the operator's "
        f"workflow automation, refreshed every {_TTL_SECONDS // 60}min, "
        f"anchored by [NOW]. for detail call the prefect_* tools.]\n{text}"
    )
    _cache["text"] = block
    _cache["fetched_at"] = now
    return block
