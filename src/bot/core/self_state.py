"""[GOALS] + [STRANGER'S AUDIT] + [SELF STATE] — phi sees its compass, its drift, and its operational pointers.

GOALS are intent: what phi is for. Stored on PDS as canonical state.
STRANGER'S AUDIT is friction: a fresh reader's critique of recent posts,
evaluated against the stated goals — patterns to push against, not maintain.
SELF STATE is operational: last follow, queue depth.

The haiku audit is *derived* (not duplicated state) and cached in memory:
1h TTL, invalidated when the latest post URI changes or goals change. The
whole compose is also block-cached at 5min so notification polls (10s)
don't hammer PDS.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from pydantic_ai import Agent

from bot.config import settings
from bot.core.atproto_client import BotClient
from bot.core.goals import list_goals as list_goal_records
from bot.utils.time import relative_when

if TYPE_CHECKING:
    from bot.memory import NamespaceMemory

logger = logging.getLogger("bot.self_state")

# Audit cache — invalidated on new post (latest URI) or goal change (signature) or TTL.
_AUDIT_TTL_SECONDS = 3600  # 1h
_audit_cache: dict = {
    "text": "",
    "fetched_at": 0.0,
    "based_on_uri": "",
    "goals_signature": "",
}

# Whole-block cache — bounds PDS lookups under high tick frequency.
_BLOCK_TTL_SECONDS = 300  # 5min
_block_cache: dict = {"text": "", "fetched_at": 0.0}

# Lazy haiku agent — performs a stranger's audit, not a characterization.
# Verb matters: "audit" surfaces friction; "characterize" produces identity.
_audit_agent: Agent | None = None


def _get_audit_agent() -> Agent:
    global _audit_agent
    if _audit_agent is None:
        _audit_agent = Agent[None, str](
            name="phi-stranger-audit",
            model=settings.extraction_model,
            system_prompt=(
                "You're a stranger who landed on this Bluesky account for the "
                "first time. You'll see recent top-level posts and (when "
                "present) the account's stated goals. Give a brief honest "
                "audit. Focus on patterns the account should push against, "
                "not maintain.\n\n"
                "Specifically flag:\n"
                "- which posts a fresh reader would find opaque (jargon, "
                "  internal references, abstract framings without grounding)\n"
                "- what's the account leaning on too heavily (one person, "
                "  one frame, one register, one source of inspiration)\n"
                "- which posts serve the stated goals vs are drift "
                "  (drift is fine; just call it out so the account sees it)\n"
                "- what's missing from the rotation that you'd want\n\n"
                "Two or three short observations, lowercase, direct. Do NOT "
                "characterize the account's voice, summarize its themes, or "
                "produce a profile — the account will read this to push "
                "against patterns, not to maintain a brand."
            ),
            output_type=str,
        )
    return _audit_agent


def _goals_signature(goals: list[dict]) -> str:
    """Stable string for goals, used to invalidate the audit when goals change."""
    return "|".join(f"{g.get('_rkey', '')}:{g.get('updated_at', '')}" for g in goals)


async def _audit_posts(posts: list[str], goals: list[dict]) -> str:
    if not posts:
        return ""
    parts = ["recent top-level posts (most recent first):", ""]
    parts.append("\n\n---\n\n".join(posts))
    if goals:
        goal_lines = "\n".join(
            f"- {g.get('title', 'untitled')}: {g.get('description', '')}" for g in goals
        )
        parts.append("\n\nthe account's stated goals:")
        parts.append(goal_lines)
    payload = "\n".join(parts)
    try:
        result = await _get_audit_agent().run(payload)
        return (result.output or "").strip()
    except Exception as e:
        logger.warning(f"stranger audit failed: {e}")
        return ""


async def _last_follow_when(client: BotClient) -> str:
    try:
        await client.authenticate()
        if not client.client.me:
            return ""
        response = client.client.com.atproto.repo.list_records(
            {
                "repo": client.client.me.did,
                "collection": "app.bsky.graph.follow",
                "limit": 1,
            }
        )
        if not response.records:
            return ""
        record = response.records[0]
        created_at = dict(record.value).get("createdAt", "") if record.value else ""
        return relative_when(created_at)
    except Exception as e:
        logger.debug(f"last_follow lookup failed: {e}")
        return ""


async def _compute_friends_progress(
    memory: NamespaceMemory | None,
) -> list[tuple[str, int]]:
    """Count handles with >=3 stored interactions in their namespace.

    Cheap check against the `make 3 friends` goal — the frozen text in the
    goal record says `currently: 0` but phi has in fact had substantive
    exchanges. This computes the objective portion of the goal's
    progress_signal live so phi reasons against current truth, not
    author-intent text.

    Excludes phi herself and the operator (nate); both match "non-nate"
    exclusion from the goal definition. Devlog is not excluded — it's
    nate's own testing account and phi can weigh it appropriately.

    Returns [(handle, exchange_count), ...] sorted by count desc.
    """
    if memory is None:
        return []
    try:
        user_prefix = f"{memory.NAMESPACES['users']}-"
        page = memory.client.namespaces(prefix=user_prefix)
    except Exception as e:
        logger.debug(f"friends-progress: listing namespaces failed: {e}")
        return []

    excluded = {settings.bluesky_handle, settings.owner_handle}
    results: list[tuple[str, int]] = []
    for ns_summary in page.namespaces:
        handle = ns_summary.id.removeprefix(user_prefix).replace("_", ".")
        if handle in excluded:
            continue
        try:
            user_ns = memory.client.namespace(ns_summary.id)
            # top_k=10 is enough to tell "has >=3"; we cap the meaningful
            # number at 10 exchanges anyway — more than that is just "a lot"
            response = user_ns.query(
                rank_by=("created_at", "desc"),
                top_k=10,
                filters={"kind": ["Eq", "interaction"]},
                include_attributes=["kind"],
            )
            count = len(response.rows) if response.rows else 0
            if count >= 3:
                results.append((handle, count))
        except Exception:
            continue

    results.sort(key=lambda t: (-t[1], t[0]))
    return results


def _format_goals_block(
    goals: list[dict], friends_progress: list[tuple[str, int]]
) -> str:
    if not goals:
        return ""
    lines = [
        "[GOALS — stored at io.zzstoatzz.phi.goal on your PDS — your "
        "anchors. work that doesn't serve these is drift, which is fine "
        "but visible. mutate via propose_goal_change with owner approval]"
    ]
    for g in goals:
        rkey = g.get("_rkey", "")
        rkey_part = f"[rkey {rkey}] " if rkey else ""
        lines.append(
            f"- {rkey_part}{g.get('title', 'untitled')}: {g.get('description', '')}"
        )
        if g.get("progress_signal"):
            lines.append(f"  (definition: {g['progress_signal']})")
        # Live-computed friends progress, appended for the make-3-friends
        # goal. Identified heuristically by title; trivial to generalize
        # later to a per-goal computed-progress map if more goals accrue.
        if "friend" in g.get("title", "").lower() and friends_progress:
            qualifying = ", ".join(
                f"@{h} ({n}+)"[:100] for h, n in friends_progress[:8]
            )
            lines.append(
                f"  current (computed): {len(friends_progress)} handles "
                f"with ≥3 exchanges — {qualifying}"
            )
        elif "friend" in g.get("title", "").lower():
            lines.append("  current (computed): 0 handles with ≥3 exchanges")
    return "\n".join(lines)


async def get_state_block(
    client: BotClient, memory: NamespaceMemory | None = None
) -> str:
    """Compose [GOALS] + [STRANGER'S AUDIT] + [SELF STATE].

    Cached at the block level (5min) and audit level (1h, invalidated on
    new post or goal change). `memory` is used to live-compute the friends
    progress count; if omitted, the computed line is skipped (goal record
    text still renders).
    """
    now = time.time()
    if _block_cache["text"] and now - _block_cache["fetched_at"] < _BLOCK_TTL_SECONDS:
        return _block_cache["text"]

    goals = await list_goal_records(client)
    friends_progress = await _compute_friends_progress(memory)
    parts: list[str] = []

    # Goals first — phi reads its anchors before reading critique of its work.
    goals_block = _format_goals_block(goals, friends_progress)
    if goals_block:
        parts.append(goals_block)

    # Stranger's audit — recent posts vs goals, accessibility check.
    try:
        feed = await client.get_own_posts(limit=10)
        posts: list[str] = []
        latest_uri = ""
        for item in feed:
            if hasattr(item.post.record, "text"):
                posts.append(item.post.record.text)
                if not latest_uri:
                    latest_uri = item.post.uri

        goals_sig = _goals_signature(goals)
        audit_stale = now - _audit_cache["fetched_at"] > _AUDIT_TTL_SECONDS
        post_changed = latest_uri != _audit_cache["based_on_uri"]
        goals_changed = goals_sig != _audit_cache["goals_signature"]
        if not _audit_cache["text"] or audit_stale or post_changed or goals_changed:
            new_audit = await _audit_posts(posts, goals)
            if new_audit:
                _audit_cache["text"] = new_audit
                _audit_cache["fetched_at"] = now
                _audit_cache["based_on_uri"] = latest_uri
                _audit_cache["goals_signature"] = goals_sig

        if _audit_cache["text"]:
            parts.append(
                "[STRANGER'S AUDIT — patterns to push against, not maintain]\n"
                f"{_audit_cache['text']}"
            )
    except Exception as e:
        logger.debug(f"stranger audit compose failed: {e}")

    # Operational pointers.
    follow_age = await _last_follow_when(client)
    if follow_age:
        parts.append(f"[SELF STATE]\nlast follow: {follow_age}")

    block = "\n\n".join(parts)
    _block_cache["text"] = block
    _block_cache["fetched_at"] = now
    return block
