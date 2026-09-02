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
# the smallest tool a provider accepts; its marginal cost is the tool-use
# preamble plus a few tokens for itself
PROBE_TOOL = ToolDefinition(name="noop", description="")
PROBE_TOOL_2 = ToolDefinition(name="noop2", description="")


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

    exact counting is marginal: the request is built up in prompt order and
    each section's weight is what it added, so sections sum to the total.
    the provider's tool-use preamble — paid once when any tool is present —
    lands in its own ``tool-use framing`` section rather than on whichever
    tool happens to come first. one counting request per section plus two;
    on any provider error it degrades to the estimate and says so.
    """
    counting: Counting = "estimated"
    if model is not None:
        try:
            text_sections = [s for s in sections if s.kind != "tool"]
            tool_sections = [s for s in sections if s.tool_def is not None]
            running = await _exact(model, _probe_message(), [])
            for i, s in enumerate(text_sections):
                if not s.text:
                    s.tokens = 0
                    continue
                now = await _exact(model, prompt_messages(text_sections[: i + 1]), [])
                s.tokens, running = max(now - running, 0), now
            framing = 0
            if tool_sections:
                # two minimal tools: the second's marginal cost is what a
                # minimal tool costs by itself, so the first's marginal cost
                # minus that is the preamble alone
                one = await _exact(model, prompt_messages(text_sections), [PROBE_TOOL])
                two = await _exact(
                    model, prompt_messages(text_sections), [PROBE_TOOL, PROBE_TOOL_2]
                )
                framing = max((one - running) - (two - one), 0)
            for i, s in enumerate(tool_sections):
                now = await _exact(
                    model,
                    prompt_messages(text_sections),
                    [t.tool_def for t in tool_sections[: i + 1] if t.tool_def],
                )
                s.tokens, running = (
                    max(now - running - (framing if i == 0 else 0), 0),
                    now,
                )
            if framing:
                sections.append(
                    ContextSection(
                        kind="tool",
                        name="tool-use framing",
                        chars=0,
                        tokens=framing,
                        origin="provider",
                    )
                )
            return "exact", running
        except NotImplementedError:
            logger.info(f"{type(model).__name__} does not count tokens; estimating")
        except Exception as e:
            logger.warning(
                f"token counting failed, estimating: {type(e).__name__}: {e}"
            )
    for s in sections:
        s.tokens = estimate_tokens(s.chars)
    return counting, sum(s.tokens for s in sections)
