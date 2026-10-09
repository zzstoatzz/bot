"""Read-only cockpit views of Phi's context and offered tool definitions."""

from __future__ import annotations

import inspect
import logging
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from pydantic_ai import RunContext
from pydantic_ai.models import infer_model
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets._tool_search import ToolSearchToolset
from pydantic_ai.usage import RunUsage

from bot.config import settings
from bot.core import model_catalog
from bot.core.abilities import risk_of
from bot.core.cache_stability import cache_monitor
from bot.core.context_tokens import ContextSection, count_context_tokens, tool_section
from bot.core.mcp_tools import _mcp_origin
from bot.tools._helpers import PhiDeps

if TYPE_CHECKING:
    from bot.agent import PhiAgent

logger = logging.getLogger("bot.context_diagnostics")


async def render_context_preview(phi: PhiAgent) -> list[dict]:
    """Render every dynamic context block as a fresh scheduled run would
    see it right now — the /diagnostic page's data source.

    Stateless by construction: a throwaway PhiDeps (no notifications
    context, its own run_cache) is exactly what a scheduled entry point
    gets, so batch-seeded blocks render empty here just as they would
    there. Blocks read their module caches like any run; nothing is
    written. A block that raises reports its error instead of taking
    the preview down.
    """
    if settings.voice_reset:
        return []
    deps = PhiDeps(author_handle="", memory=phi.memory)
    ctx = cast(RunContext[PhiDeps], SimpleNamespace(deps=deps))

    static_text = await phi.personality_instructions(ctx)
    blocks: list[dict] = [
        {
            "name": "static_instructions",
            "text": static_text,
            "chars": len(static_text),
            "ms": 0.0,
            "error": None,
        }
    ]
    for name, block in phi.context_blocks:
        t0 = time.perf_counter()
        text, error = "", None
        try:
            text = await block(ctx)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        blocks.append(
            {
                "name": name,
                "text": text,
                "chars": len(text),
                "ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": error,
            }
        )
    return blocks

async def list_tool_definitions(phi: PhiAgent) -> list[tuple[str, ToolDefinition]]:
    """every tool definition the next run would send, tagged with where
    it comes from: ``function`` for @agent.tool registrations, ``skills``
    for the skills toolset, ``mcp:<prefix>`` per MCP server. MCP servers
    are connected the same way a run connects them and released after
    listing; one that is down costs its tools, not the listing."""
    if settings.voice_reset:
        return []

    # a real RunContext: toolsets `replace()` it per tool and read
    # `retries`, so a stand-in namespace is not enough here
    deps = PhiDeps(author_handle="", memory=phi.memory)
    model = phi.agent.model
    assert model is not None
    ctx = RunContext[PhiDeps](deps=deps, model=infer_model(model), usage=RunUsage())
    out: list[tuple[str, ToolDefinition]] = []
    for name in sorted(phi.agent._function_toolset.tools):
        out.append(("function", phi.agent._function_toolset.tools[name].tool_def))
    for name, tool in sorted((await phi.skills_toolset.get_tools(ctx)).items()):
        out.append(("skills", tool.tool_def))
    sent = {tool_def.name for _, tool_def in out}
    for ts in phi._mcp_toolsets(run_label="context-budget"):
        origin = f"mcp:{_mcp_origin(ts)}"
        # deferred tools are not sent; the search tool that finds them is
        visible = ToolSearchToolset(wrapped=ts)
        try:
            async with ts:
                for name, tool in sorted((await visible.get_tools(ctx)).items()):
                    if name not in sent:
                        sent.add(name)
                        out.append((origin, tool.tool_def))
        except Exception as e:
            logger.warning(
                f"{origin} unavailable for the context budget: {type(e).__name__}: {str(e)[:120]}"
            )
    return out

async def render_context_budget(phi: PhiAgent) -> dict:
    """what the next scheduled run would send, weighed: the model and its
    window from the catalog, every section with a token count, and the
    provider's own numbers from the last real run for comparison. the
    operator page's context panel reads this."""
    blocks = await phi.render_context_preview()
    sections: list[ContextSection] = []
    for b in blocks:
        sections.append(
            ContextSection(
                kind="static" if b["name"] == "static_instructions" else "block",
                name=b["name"],
                chars=b["chars"],
                ms=b["ms"],
                error=b["error"],
                text=b["text"],
            )
        )
    for origin, tool_def in await phi.list_tool_definitions():
        sections.append(tool_section(tool_def, origin))

    model = None
    if not settings.voice_reset and not isinstance(phi.agent.model, str):
        model = phi.agent.model
    counting, prompt_total = await count_context_tokens(model, sections)
    limits = await model_catalog.lookup_model_limits(settings.agent_model)
    totals = {
        "static": sum(s.tokens for s in sections if s.kind == "static"),
        "blocks": sum(s.tokens for s in sections if s.kind == "block"),
        "tools": sum(s.tokens for s in sections if s.kind == "tool"),
        "prompt": prompt_total,
    }
    last = next((r for r in reversed(cache_monitor.runs) if r.samples), None)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "path": "voice reset (context disabled)"
        if settings.voice_reset
        else "scheduled (no notifications batch)",
        "voice_reset": settings.voice_reset,
        "model": limits.as_dict(),
        "counting": counting,
        "sections": [s.as_dict() for s in sections],
        "totals": totals,
        "recent": cache_monitor.request_sizes(),
        "last_run": None
        if last is None
        else {
            "label": last.label,
            "started_at": last.started_at.isoformat(),
            "model": last.samples[0].model,
            "trace_url": last.as_dict()["trace_url"],
            "requests": [
                {
                    "input_tokens": r.uncached,  # Cockpit field means uncached input.
                    "cache_read": r.cache_read,
                    "cache_write": r.cache_write,
                    "billed_prefix": r.billed_prefix,
                }
                for r in last.samples
            ],
        },
    }


def get_capabilities(phi: PhiAgent) -> list[dict]:
    """Plain-data introspection of phi's registered function-tools.

    Reads from `phi.agent._function_toolset.tools` (where pydantic-ai
    stores the registered `@agent.tool` callables). Returns one entry
    per tool with:
      - name: the registered tool name
      - description: the tool's docstring (what gets sent to the LLM)
      - operator_only: heuristic — true if the tool is gated to the
        bot's owner. Detected via either an `_is_owner(` source-call
        or owner-restriction phrasing in the docstring. When an
        explicit owner-gating attribute lands on `Tool`, swap this
        heuristic for a direct read.

    Surfaced via /api/abilities so the cockpit UI can render real
    names + real docstrings instead of inventing them.
    """
    tools = phi.agent._function_toolset.tools
    out: list[dict] = []
    for name in sorted(tools.keys()):
        t = tools[name]
        try:
            src = inspect.getsource(t.function)
        except (OSError, TypeError):
            src = ""
        doc = (t.description or "").strip()
        doc_lower = doc.lower()
        operator_only = "_is_owner(" in src or any(
            marker in doc_lower
            for marker in (
                "owner-only",
                "only the bot's owner",
                "operator-only",
                "only @",
            )
        )
        out.append(
            {
                "name": name,
                "description": doc,
                "operator_only": operator_only,
                # required by lexicons/io/zzstoatzz/phi/getAbilities.json —
                # tests/test_abilities.py fails if any registered tool
                # lacks a declaration, so this is never None in practice
                "risk": risk_of(name),
            }
        )
    return out
