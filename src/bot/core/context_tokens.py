"""Token weight of what phi's next run would send, section by section.

A section is one thing the model reads: the static instructions, one
dynamic context block, or one tool definition. Counting is exact when the
configured model implements pydantic-ai's ``Model.count_tokens`` (Anthropic,
Google, Bedrock) and an estimate of four characters per token otherwise;
the result carries which, and the panel says so. The whole-prompt count is
one request with every section in place, so it includes framing the
per-section counts cannot see (tool-use preamble, cache markers).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Literal

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    SystemPromptPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.tools import ToolDefinition

logger = logging.getLogger("bot.context_tokens")

Counting = Literal["exact", "estimated"]
SectionKind = Literal["static", "block", "tool"]

CHARS_PER_TOKEN = 4


@dataclass
class ContextSection:
    kind: SectionKind
    name: str
    chars: int
    tokens: int = 0
    ms: float = 0.0
    error: str | None = None
    origin: str = ""
    text: str = ""
    tool_def: ToolDefinition | None = field(default=None, repr=False)

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "name": self.name,
            "chars": self.chars,
            "tokens": self.tokens,
            "ms": self.ms,
            "error": self.error,
            "origin": self.origin,
        }


def tool_section(tool_def: ToolDefinition, origin: str) -> ContextSection:
    rendered = json.dumps(
        {
            "name": tool_def.name,
            "description": tool_def.description or "",
            "input_schema": tool_def.parameters_json_schema,
        },
        separators=(",", ":"),
    )
    return ContextSection(
        kind="tool",
        name=tool_def.name,
        chars=len(rendered),
        origin=origin,
        text=rendered,
        tool_def=tool_def,
    )


def estimate_tokens(chars: int) -> int:
    return -(-chars // CHARS_PER_TOKEN) if chars else 0


# providers reject whitespace-only text blocks, so the constant frame every
# probe carries is a single period; the baseline probe measures it and
# section counts are the difference
PROBE_FRAME = "."


def _probe_message(text: str = "") -> list[ModelMessage]:
    return [ModelRequest(parts=[UserPromptPart(content=PROBE_FRAME + text)])]


async def _exact(
    model: Model, messages: list[ModelMessage], tools: list[ToolDefinition]
) -> int:
    usage = await model.count_tokens(
        messages, None, ModelRequestParameters(function_tools=tools)
    )
    return usage.input_tokens


def prompt_messages(sections: list[ContextSection]) -> list[ModelMessage]:
    """the next run's request as pydantic-ai would send it: every text
    section as its own system part, then an empty user turn."""
    parts = [
        SystemPromptPart(content=s.text)
        for s in sections
        if s.kind != "tool" and s.text
    ]
    return [ModelRequest(parts=[*parts, UserPromptPart(content=PROBE_FRAME)])]


async def count_context_tokens(
    model: Model | None, sections: list[ContextSection]
) -> tuple[Counting, int]:
    """fill in ``tokens`` on every section; returns (counting, prompt_total).

    exact counting costs one request per section plus one for the whole
    prompt; on any provider error it degrades to the estimate for the rest
    and reports ``estimated``.
    """
    tools = [s.tool_def for s in sections if s.tool_def is not None]
    counting: Counting = "estimated"
    if model is not None:
        try:
            baseline = await _exact(model, _probe_message(), [])
            for s in sections:
                if s.tool_def is not None:
                    s.tokens = max(
                        await _exact(model, _probe_message(), [s.tool_def]) - baseline,
                        0,
                    )
                elif s.text:
                    s.tokens = max(
                        await _exact(model, _probe_message(s.text), []) - baseline, 0
                    )
                else:
                    s.tokens = 0
            total = await _exact(model, prompt_messages(sections), tools)
            return "exact", total
        except NotImplementedError:
            logger.info(f"{type(model).__name__} does not count tokens; estimating")
        except Exception as e:
            logger.warning(
                f"token counting failed, estimating: {type(e).__name__}: {e}"
            )
    for s in sections:
        s.tokens = estimate_tokens(s.chars)
    return counting, sum(s.tokens for s in sections)
