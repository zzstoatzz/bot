"""Phi delegates approved maintenance work to Gardener through Prefect."""

from typing import Annotated, Literal

import httpx
from pydantic import Field
from pydantic_ai import RunContext

from bot.config import settings
from bot.core import workflow_receipts
from bot.core.override import get_override, refusal_text
from bot.tools._helpers import PhiDeps, _is_owner

Repo = Literal["my-prefect-server", "find-bufo", "plyr.fm", "bot"]
Workflow = Literal["investigate", "propose-change"]
WORKFLOWS = {"investigate", "propose-change"}


def register(agent):
    @agent.tool
    async def request_workflow(
        ctx: RunContext[PhiDeps],
        workflow: Annotated[
            Workflow,
            Field(
                description="Investigate with read-only tools, or propose a code patch for review"
            ),
        ],
        instructions: Annotated[
            str,
            Field(
                min_length=1,
                description="Self-contained task for Gardener; include the facts and expected outcome",
            ),
        ],
        repo: Annotated[Repo, Field(description="Repository the workflow operates on")],
        request_key: Annotated[
            str,
            Field(
                min_length=1,
                description="Stable identity of this request, such as its source post URI; reuse when retrying",
            ),
        ],
        title: Annotated[
            str, Field(description="For propose-change: proposed pull title")
        ] = "",
        body: Annotated[
            str,
            Field(description="For propose-change: purpose and acceptance criteria"),
        ] = "",
    ) -> dict:
        """Queue an owner-authorized workflow and return its Prefect run ID.

        Gardener (gardener.pds.zat.dev) investigates and proposes changes using
        the Pi harness in a Sprite. Phi requests and reviews the work; the
        trusted workflow publishes as Gardener. Merging requires the operator.
        Use prefect_get_flow_runs and prefect_get_flow_run_logs to follow the ID.
        Reuse request_key for retries so an uncertain response cannot duplicate work.
        In an operator DM, use operator_workflow_status to recover receipts and
        check progress. The request permits only the described investigation or
        proposal; it does not authorize merging or deployment.
        """
        if not _is_owner(ctx):
            return {
                "queued": False,
                "reason": "Only the operator can queue a workflow from this run. "
                "It is fine to ask them; report_operator with a note: key is "
                "the private route.",
            }
        override = await get_override()
        if override["active"]:
            return {"queued": False, "reason": refusal_text(override)}
        if workflow not in WORKFLOWS or repo not in Repo.__args__:
            raise ValueError("Unsupported workflow or repository")
        if not instructions.strip() or not request_key.strip():
            raise ValueError("Instructions and request_key are required")
        if workflow == "propose-change" and (not title.strip() or not body.strip()):
            raise ValueError("A proposed change requires a title and body")
        if not settings.workflow_request_token:
            return {
                "queued": False,
                "reason": "Workflow authentication is not configured",
            }
        payload = {
            "workflow": workflow,
            "instructions": instructions,
            "repo": repo,
            "request_key": request_key,
            "title": title.strip(),
            "body": body.strip(),
        }
        try:
            receipt = workflow_receipts.reserve(
                payload, getattr(getattr(ctx, "deps", None), "private_message_id", "")
            )
        except ValueError:
            return {
                "queued": False,
                "reason": "This request key identifies different work. Review the changed action with the operator before using a new key.",
            }
        if receipt["state"] == "queued":
            return {
                "queued": True,
                "flow_run_id": receipt["flow_run_id"],
                "name": receipt["run_name"],
                "workflow": workflow,
                "request_key": request_key,
            }
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                response = await http.post(
                    settings.workflow_request_url,
                    headers={
                        "Authorization": "Bearer "
                        + settings.workflow_request_token.get_secret_value()
                    },
                    json=payload,
                )
                response.raise_for_status()
                run = response.json()
                if not isinstance(run, dict) or not all(
                    isinstance(run.get(k), str) and run[k]
                    for k in ("flow_run_id", "name")
                ):
                    raise ValueError("Incomplete workflow receipt")
        except (httpx.HTTPError, ValueError):
            return {
                "queued": False,
                "reason": "Prefect did not confirm the request; retry with the same request_key",
            }
        workflow_receipts.confirm(request_key, run["flow_run_id"], run["name"])
        return {
            "request_key": request_key,
            "queued": True,
            "flow_run_id": run["flow_run_id"],
            "name": run["name"],
            "workflow": workflow,
        }

    @agent.tool
    async def operator_workflow_status(
        ctx: RunContext[PhiDeps],
        request_key: Annotated[
            str,
            Field(
                description="Exact request key; omit to inspect the ten latest local workflow receipts"
            ),
        ] = "",
    ) -> dict:
        """Inspect requested work and current Prefect state in the operator DM.

        Receipts are private. Queued is not completed; completed is not merged
        or deployed. Inspect the run's evidence before claiming an outcome.
        No dispatch or retry occurs here. An unconfirmed receipt may represent
        accepted work; do not create another request to find out.
        """
        if not _is_owner(ctx) or not ctx.deps.private_message_id:
            return {
                "error": "Workflow receipts are only available in the private operator conversation."
            }
        receipts = workflow_receipts.recent(request_key)
        auth = settings.prefect_api_auth_string
        async with httpx.AsyncClient(timeout=15) as http:
            for receipt in receipts:
                run_id = receipt["flow_run_id"]
                if not run_id or not auth or ":" not in auth:
                    receipt["live_status"] = "unavailable"
                    continue
                try:
                    response = await http.get(
                        f"{settings.prefect_api_url.rstrip('/')}/flow_runs/{run_id}",
                        auth=httpx.BasicAuth(
                            auth.split(":", 1)[0], auth.split(":", 1)[1]
                        ),
                    )
                    response.raise_for_status()
                    run = response.json()
                    if not isinstance(run, dict) or not isinstance(
                        run.get("state_type"), str
                    ):
                        raise ValueError("Incomplete workflow state")
                    receipt["live_status"] = {
                        k: run.get(k)
                        for k in ("state_type", "state_name", "start_time", "end_time")
                    }
                except (httpx.HTTPError, ValueError):
                    receipt["live_status"] = "unavailable"
        return {
            "requests": receipts,
            "coverage": "Local receipts since this feature was enabled; absence is not proof that no earlier work exists.",
        }
