"""MCP server construction, exposure and wrapper inspection for Phi runs."""

from pathlib import Path
from typing import Any

from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP
from pydantic_ai.toolsets import AbstractToolset

from bot.config import settings
from bot.core.mcp_guard import make_mcp_guard
from bot.tools._helpers import PhiDeps

# What phi carries from each MCP server (docs/toolset-audit-2026-10.md).
# prefect and pub-search expose a surface built for people working on those
# services, so she gets an allowlist. tangled and pdsx lose named tools.
MCP_KEPT: dict[str, frozenset[str]] = {
    "prefect": frozenset(
        {
            "prefect_get_flow_runs",
            "prefect_get_flow_run_logs",
            "prefect_get_deployments",
            "prefect_get_flows",
        }
    ),
    "pub-search": frozenset(
        {"pub_search", "pub_get_document", "pub_discover_focal_post"}
    ),
}
MCP_DROPPED: dict[str, frozenset[str]] = {
    "pdsx": frozenset({"whoami"}),
    "tangled": frozenset(
        {
            "tangled_set_pull_state",
            "tangled_list_pulls",
            "tangled_update_issue",
            "tangled_set_issue_state",
            "tangled_delete_issue",
            "tangled_list_pipelines",
            "tangled_list_tags",
        }
    ),
}


# Servers phi reaches for in about one run in a hundred. Their tools stay out
# of the request until she finds them with `search_tools`, except in a run
# whose prompt sends her straight to them.
MCP_DEFERRED: dict[str, frozenset[str]] = {
    "tangled": frozenset({"pull request comment", "pull request review"}),
    "lexidraw": frozenset(),
}


def _offered(
    server: str, toolset: AbstractToolset[PhiDeps], run_label: str = ""
) -> AbstractToolset[PhiDeps]:
    """Narrow an MCP server to the tools phi carries from it for this run."""
    if kept := MCP_KEPT.get(server):
        toolset = toolset.filtered(lambda _ctx, tool: tool.name in kept)
    elif dropped := MCP_DROPPED.get(server):
        toolset = toolset.filtered(lambda _ctx, tool: tool.name not in dropped)
    loaded_for = MCP_DEFERRED.get(server)
    if loaded_for is not None and run_label not in loaded_for:
        toolset = toolset.defer_loading()
    return toolset


def _mcp_url(toolset: AbstractToolset[Any]) -> str | None:
    """The server URL behind a toolset, through any wrappers around it."""
    while (wrapped := getattr(toolset, "wrapped", None)) is not None:
        toolset = wrapped
    return getattr(toolset, "url", None)


def _mcp_origin(ts: AbstractToolset[Any]) -> str:
    """a short name for where a tool came from: the tool prefix when the
    server has one, else the host's first label or the stdio command."""
    while (wrapped := getattr(ts, "wrapped", None)) is not None:
        ts = wrapped
    if prefix := getattr(ts, "tool_prefix", None):
        return str(prefix)
    if url := getattr(ts, "url", None):
        return str(url).split("//", 1)[-1].split("/", 1)[0].split(".", 1)[0]
    if args := getattr(ts, "args", None):
        parts = [p for p in str(list(args)[-1]).split("/") if p]
        named = [p for p in parts if p not in ("dist", "build", "bin", "opt", "app")]
        return named[-2] if len(named) > 1 else (named[0] if named else "stdio")
    return ts.label


def build_toolsets(run_label: str = "") -> list[AbstractToolset[PhiDeps]]:
    """Create fresh MCP server instances for a single agent run."""
    toolsets: list[AbstractToolset[PhiDeps]] = [
        _offered(
            "pdsx",
            MCPServerStreamableHTTP(
                url="https://pdsx-by-zzstoatzz.fastmcp.app/mcp",
                timeout=30,
                headers={
                    "x-atproto-handle": settings.bluesky_handle,
                    "x-atproto-password": settings.bluesky_password,
                },
                # structural guard: raw feed-collection writes bypass the
                # consent layer / policy judge / operator override — refuse
                # them here, not just in the prompt (bot/core/mcp_guard.py)
                process_tool_call=make_mcp_guard("pdsx", run_label),
            ),
        ),
        _offered(
            "pub-search",
            MCPServerStreamableHTTP(
                url="https://pub-search-by-zzstoatzz.fastmcp.app/mcp",
                timeout=30,
                tool_prefix="pub",
                process_tool_call=make_mcp_guard("pub-search", run_label),
            ),
        ),
        # Semble jev-mode server (search_tools/call_tool; one sdk method
        # per call). Keyless = public reads only; the header makes
        # writes attribute to phi.
        MCPServerStreamableHTTP(
            url=settings.semble_mcp_url,
            timeout=30,
            tool_prefix="semble",
            headers=(
                {"x-semble-api-key": settings.semble_api_key}
                if settings.semble_api_key
                else {}
            ),
            # observational: every library write leaves a logfire event
            # with the run label + the sdk method (bot/core/mcp_guard.py)
            process_tool_call=make_mcp_guard("semble", run_label),
        ),
        # Tangled code-collab server. Reads (repos, files, commits,
        # issues) need no auth; the headers carry phi's own PDS
        # credentials so any issue/comment she writes attributes to her.
        _offered(
            "tangled",
            MCPServerStreamableHTTP(
                url=settings.tangled_mcp_url,
                timeout=30,
                tool_prefix="tangled",
                headers={
                    "x-tangled-handle": settings.bluesky_handle,
                    "x-tangled-password": settings.bluesky_password,
                },
                # issues and comments here are public actions in phi's own
                # name; before 2026-07-25 nothing gated them, so safe mode
                # stopped her posting to bluesky and left tangled open.
                process_tool_call=make_mcp_guard("tangled", run_label),
            ),
            run_label,
        ),
    ]
    # Lexidraw — phi draws into her own repo (app.lexidraw.scene records,
    # viewable at lexidraw.app). Stdio server baked into the image; her
    # own credentials, so scenes attribute to her. lexidraw_save is a
    # public artifact in her name → guard treats it as a mutation.
    if Path(settings.lexidraw_mcp_path).exists():
        toolsets.append(
            _offered(
                "lexidraw",
                MCPServerStdio(
                    "node",
                    args=[settings.lexidraw_mcp_path],
                    env={
                        "LEXIDRAW_HANDLE": settings.bluesky_handle,
                        "LEXIDRAW_APP_PASSWORD": settings.bluesky_password,
                    },
                    timeout=30,
                    process_tool_call=make_mcp_guard("lexidraw", run_label),
                ),
                run_label,
            )
        )
    # Prefect MCP — only included when auth is configured, so phi degrades
    # gracefully in dev/local without the secret set.
    if settings.prefect_api_auth_string:
        toolsets.append(
            _offered(
                "prefect",
                MCPServerStreamableHTTP(
                    url=settings.prefect_mcp_url,
                    timeout=30,
                    tool_prefix="prefect",
                    process_tool_call=make_mcp_guard("prefect", run_label),
                    headers={
                        "x-prefect-api-url": settings.prefect_api_url,
                        "x-prefect-api-auth-string": settings.prefect_api_auth_string,
                    },
                ),
            )
        )
    return toolsets

