"""Current goals and a separately rendered, derived posting inventory."""

import asyncio
import json
import logging
import time
from pathlib import Path

from pydantic_ai import Agent

from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.core.goals import FIELD_CAPS
from bot.core.goals import list_goals as list_goal_records
from bot.memory import NamespaceMemory

logger = logging.getLogger("bot.self_state")

# Recent-posting inventory cache, invalidated on new post (latest URI) or TTL.
# Persisted so a restart does not recompile; overlapping renders share one call.
_INVENTORY_TTL_SECONDS = 3600  # 1h
INVENTORY_CACHE_FILE = Path("/data/posting_inventory.json")
_inventory_cache: dict | None = None
_inventory_inflight: dict[str, asyncio.Task[str]] = {}

# Whole-block cache — bounds PDS lookups under high tick frequency.
_BLOCK_TTL_SECONDS = 300  # 5min
_block_cache: dict = {"text": "", "fetched_at": 0.0}


def invalidate_state_cache() -> None:
    """Force [GOALS] to recompose on the next read.

    Called by goal mutation tools (propose_goal_change, update_goal_progress)
    so phi doesn't see her own just-written progress as stale for up to 5min
    after a write.
    """
    _block_cache["text"] = ""
    _block_cache["fetched_at"] = 0.0


# Lazy haiku agent — compiles a recent-posting inventory. Deliberately
# not framed as a "voice" or "critic": its output is structured field /
# value pairs in plain English, third person, no first-person rhetoric.
# Why: this block is read every cycle as "what your recent posts have
# been about," and if it speaks in phi's register the model will
# reinforce that register as identity. Stay boring.
_inventory_agent: Agent | None = None


def _get_inventory_agent() -> Agent:
    global _inventory_agent
    if _inventory_agent is None:
        _inventory_agent = Agent[None, str](
            name="phi-posting-inventory",
            model=settings.extraction_model,
            system_prompt=(
                "You are a lab tech compiling a recent-posting inventory of "
                "phi's top-level posts. The output is a structured tally, not "
                "phi's voice — phi will read this as descriptive context, so "
                "any rhetoric here teaches her to imitate it.\n\n"
                "RULES:\n"
                "- third person, no first person.\n"
                "- no em-dashes.\n"
                "- no abstract noun phrases like 'structural questions about "
                "X,' 'the substrate of Y,' or 'X relocates Y.'\n"
                "- no rhetorical openings like 'recent posts have circled.'\n"
                "- no 'X isn't Y, it's Z' constructions.\n"
                "- prefer concrete words: actual subjects, actual handles, "
                "actual posting mode.\n\n"
                "OUTPUT exactly three lines, this format, no extra prose:\n\n"
                "subjects: <2-5 concrete topics, semicolons between>\n"
                "people: <@handles phi referenced by name, commas between, or 'none'>\n"
                "mode: <one short categorical phrase, e.g. 'mostly posts "
                "about tools and meetups', 'mostly replies about workflow', "
                "'reactive replies to specific posts', 'short observations'>\n"
                "Describe only the supplied posts. If a field has nothing to report, "
                "write 'none'."
            ),
            output_type=str,
        )
    agent = _inventory_agent
    assert agent is not None
    return agent


async def _compile_inventory(posts: list[str]) -> str:
    """Compile a third-person recent-posting inventory from phi's top-level posts."""
    if not posts:
        return ""
    payload = (
        "phi's recent top-level posts (most recent first):\n\n"
        + "\n\n---\n\n".join(posts)
    )
    try:
        result = await _get_inventory_agent().run(payload)
        return (result.output or "").strip()
    except Exception as e:
        logger.warning(f"posting inventory compile failed: {e}")
        return ""


def _clamp(text: str, cap: int) -> str:
    """Visible truncation for field values written before the caps existed.
    New writes are rejected over-cap at the tool, so this marker is also
    the nudge to rewrite the field within its budget."""
    if len(text) <= cap:
        return text
    return text[: cap - 1] + f"… [cut at {cap} chars — rewrite this field tighter]"


def _format_goals_block(goals: list[dict]) -> str:
    if not goals:
        return ""
    lines = [
        "[GOALS — io.zzstoatzz.phi.goal. Operator-approved scope; "
        "progress and next steps are your account, not verified live state. "
        "Relative dates inside a saved note refer to when it was recorded.]"
    ]
    for g in goals:
        rkey = g.get("_rkey", "")
        rkey_part = f"[rkey {rkey}] " if rkey else ""
        kind = g.get("kind", "goal")
        lines.append(f"- {rkey_part}{g.get('title', 'untitled')} ({kind})")
        if g.get("description"):
            lines.append(f"  why: {g['description']}")
        if g.get("metabolism"):
            lines.append(f"  metabolism: {g['metabolism']}")
        if g.get("progress_signal"):
            clamped = _clamp(g["progress_signal"], FIELD_CAPS["progress_signal"])
            lines.append(f"  progress means (yours to revise): {clamped}")
        if g.get("current_state"):
            clamped = _clamp(g["current_state"], FIELD_CAPS["current_state"])
            lines.append(f"  current: {clamped}")
        if g.get("next_step"):
            lines.append(
                f"  next step: {_clamp(g['next_step'], FIELD_CAPS['next_step'])}"
            )
        last_step = g.get("last_step")
        last_step_at = g.get("last_step_at", "")
        if last_step:
            age_part = f"recorded {last_step_at} — " if last_step_at else ""
            lines.append(
                f"  last step: {age_part}{_clamp(last_step, FIELD_CAPS['last_step'])}"
            )
        if g.get("blocked_by"):
            lines.append(f"  blocked: {g['blocked_by']}")
    return "\n".join(lines)


async def get_state_block(
    client: BotClient, memory: NamespaceMemory | None = None
) -> str:
    """Compose [GOALS]. Cached 5min. `memory` is unused (kept for call
    compatibility; the live-computed friends line was deleted 2026-08-07 —
    it contradicted the goal's own phi-maintained `current` field)."""
    now = time.time()
    if _block_cache["text"] and now - _block_cache["fetched_at"] < _BLOCK_TTL_SECONDS:
        return _block_cache["text"]

    goals = await list_goal_records(client)
    block = _format_goals_block(goals)
    _block_cache["text"] = block
    _block_cache["fetched_at"] = now
    return block


def _load_inventory() -> dict:
    global _inventory_cache
    if _inventory_cache is None:
        try:
            _inventory_cache = json.loads(INVENTORY_CACHE_FILE.read_text())
        except FileNotFoundError:
            _inventory_cache = {}
        except (OSError, ValueError) as e:
            logger.warning(f"posting inventory cache unreadable: {e}")
            _inventory_cache = {}
    return _inventory_cache


def _save_inventory(cache: dict) -> None:
    try:
        tmp = INVENTORY_CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache))
        tmp.replace(INVENTORY_CACHE_FILE)
    except OSError as e:
        logger.warning(f"posting inventory cache not saved: {e}")


def _compile_once(latest_uri: str, posts: list[str]) -> asyncio.Task[str]:
    task = _inventory_inflight.get(latest_uri)
    if task is None:
        task = asyncio.ensure_future(_compile_inventory(posts))
        _inventory_inflight[latest_uri] = task
        task.add_done_callback(lambda _: _inventory_inflight.pop(latest_uri, None))
    return task


async def get_inventory_block(client: BotClient) -> str:
    """Recent posting topics, cached 1h or until the latest post changes."""
    now = time.time()
    try:
        feed = await client.get_own_posts(limit=10)
        posts: list[str] = []
        latest_uri = ""
        for item in feed:
            if hasattr(item.post.record, "text"):
                posts.append(item.post.record.text)
                if not latest_uri:
                    latest_uri = item.post.uri

        cache = _load_inventory()
        cache_stale = now - cache.get("fetched_at", 0.0) > _INVENTORY_TTL_SECONDS
        post_changed = latest_uri != cache.get("based_on_uri", "")
        if not cache.get("text") or cache_stale or post_changed:
            new_inventory = await asyncio.shield(_compile_once(latest_uri, posts))
            if new_inventory:
                cache.update(
                    text=new_inventory, fetched_at=now, based_on_uri=latest_uri
                )
                _save_inventory(cache)

        if cache.get("text"):
            return (
                "[POSTING INVENTORY — derived from your last 10 top-level posts; "
                "a description of activity, not identity or a writing example.]\n"
                + cache["text"]
            )
    except Exception as e:
        logger.debug(f"posting inventory compose failed: {e}")
    return ""
