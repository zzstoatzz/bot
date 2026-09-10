"""Phi requests approved Prefect workflows; Pi executes them elsewhere."""

from typing import Annotated, Literal

import httpx
from pydantic import Field
from pydantic_ai import RunContext

from bot.config import settings
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
                description="Self-contained task for Pi; include the facts and expected outcome",
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

        Phi requests the work; Pi executes in a Sprite. Gardener publishes
        proposed patches, Phi reviews them, and merging still requires a human.
        Use prefect_get_flow_runs and prefect_get_flow_run_logs to follow the ID.
        Reuse request_key for retries so an uncertain response cannot duplicate work.
        """
        if not _is_owner(ctx):
            return {
                "queued": False,
                "reason": "Workflow requests require operator authorization",
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
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                response = await http.post(
                    settings.workflow_request_url,
                    headers={
                        "Authorization": "Bearer "
                        + settings.workflow_request_token.get_secret_value()
                    },
                    json={
                        "workflow": workflow,
                        "instructions": instructions,
                        "repo": repo,
                        "request_key": request_key,
                        "title": title.strip(),
                        "body": body.strip(),
                    },
                )
                response.raise_for_status()
                run = response.json()
        except httpx.HTTPError:
            return {
                "queued": False,
                "reason": "Prefect did not confirm the request; retry with the same request_key",
            }
        return {
            "queued": True,
            "flow_run_id": run["flow_run_id"],
            "name": run["name"],
            "workflow": workflow,
        }
