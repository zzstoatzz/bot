"""[SELF STATE] block — phi's view of its own recent posting pattern, queue, and engagement.

Sources are canonical: posts/follows live on PDS, the haiku summary is *derived*
from those posts and cached in-memory (regeneratable, not duplicated state).
"""

import logging
import time
from datetime import UTC, datetime

from pydantic_ai import Agent

from bot.config import settings
from bot.core.atproto_client import BotClient

logger = logging.getLogger("bot.self_state")

# Haiku summary cache — invalidated by new post (latest URI changes) or TTL.
_SUMMARY_TTL_SECONDS = 3600  # 1h
_summary_cache: dict = {"text": "", "fetched_at": 0.0, "based_on_uri": ""}

# Whole-block cache — re-renders at most every few minutes so dynamic system
# prompts firing on every notification poll (10s) don't hammer PDS.
_BLOCK_TTL_SECONDS = 300  # 5min
_block_cache: dict = {"text": "", "fetched_at": 0.0}

# Lazy haiku agent — characterizes recent posts as if from a fresh observer.
# Framing is intentional: phi sees how its voice lands to someone with no prior
# context, which is also how strangers actually encounter the timeline.
_summary_agent: Agent | None = None


def _get_summary_agent() -> Agent:
    global _summary_agent
    if _summary_agent is None:
        _summary_agent = Agent[None, str](
            name="phi-self-summary",
            model=settings.extraction_model,
            system_prompt=(
                "You read recent top-level posts from a single Bluesky account "
                "and characterize what they've been writing about lately, as if "
                "you're a fresh observer who's never seen this account before. "
                "Lowercase. No preamble, no meta-commentary, no quoting back. "
                "Two or three short observations max. Note: themes, recurring "
                "beats, who they reference, anything notable (concentration on "
                "one topic or person, absences from usual variety, "
                "grounded-vs-pattern-matched balance)."
            ),
            output_type=str,
        )
    return _summary_agent


async def _summarize_posts(posts: list[str]) -> str:
    if not posts:
        return ""
    payload = "\n\n---\n\n".join(posts)
    try:
        result = await _get_summary_agent().run(payload)
        return (result.output or "").strip()
    except Exception as e:
        logger.warning(f"haiku summary failed: {e}")
        return ""


def _relative_when(iso_ts: str) -> str:
    """Human-readable age from an ISO timestamp."""
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ""
    delta = datetime.now(UTC) - ts
    days = delta.days
    if days < 0:
        return ""
    if days == 0:
        hours = delta.seconds // 3600
        return f"{hours}h ago" if hours else "just now"
    if days == 1:
        return "1d ago"
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    return f"{months}mo ago" if months < 12 else f"{days // 365}y ago"


async def _last_follow_when(client: BotClient) -> str:
    """Look up the most recent app.bsky.graph.follow record on phi's PDS."""
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
        return _relative_when(created_at)
    except Exception as e:
        logger.debug(f"last_follow lookup failed: {e}")
        return ""


async def _queue_depth(client: BotClient) -> int:
    """Count pending items in phi's curiosity queue."""
    try:
        await client.authenticate()
        if not client.client.me:
            return 0
        response = client.client.com.atproto.repo.list_records(
            {
                "repo": client.client.me.did,
                "collection": "io.zzstoatzz.phi.curiosityQueue",
                "limit": 100,
            }
        )
        return sum(
            1 for r in response.records if dict(r.value).get("status") == "pending"
        )
    except Exception as e:
        logger.debug(f"queue depth lookup failed: {e}")
        return 0


async def get_state_block(client: BotClient) -> str:
    """Compose the [SELF STATE] block.

    Returns the cached block text when fresh; recomputes from canonical PDS
    state otherwise. The haiku summary inside is cached separately (longer TTL,
    URI-invalidated) so we don't regenerate it on every block refresh.
    """
    now = time.time()
    if _block_cache["text"] and now - _block_cache["fetched_at"] < _BLOCK_TTL_SECONDS:
        return _block_cache["text"]

    parts: list[str] = []

    # Posting pattern — fresh-observer characterization of last 10 posts.
    try:
        feed = await client.get_own_posts(limit=10)
        posts: list[str] = []
        latest_uri = ""
        for item in feed:
            if hasattr(item.post.record, "text"):
                posts.append(item.post.record.text)
                if not latest_uri:
                    latest_uri = item.post.uri

        summary_stale = now - _summary_cache["fetched_at"] > _SUMMARY_TTL_SECONDS
        summary_invalid = latest_uri != _summary_cache["based_on_uri"]
        if not _summary_cache["text"] or summary_stale or summary_invalid:
            new_summary = await _summarize_posts(posts)
            if new_summary:
                _summary_cache["text"] = new_summary
                _summary_cache["fetched_at"] = now
                _summary_cache["based_on_uri"] = latest_uri

        if _summary_cache["text"]:
            parts.append(
                "[POSTING PATTERN — fresh observer, last 10 posts]\n"
                f"{_summary_cache['text']}"
            )
    except Exception as e:
        logger.debug(f"posting-pattern compose failed: {e}")

    # Last follow + queue depth (canonical PDS state)
    follow_age = await _last_follow_when(client)
    queue_n = await _queue_depth(client)

    misc: list[str] = []
    if follow_age:
        misc.append(f"last follow: {follow_age}")
    if queue_n > 0:
        misc.append(f"exploration queue: {queue_n} pending")
    if misc:
        parts.append(" | ".join(misc))

    block = "[SELF STATE]\n" + "\n\n".join(parts) if parts else ""
    _block_cache["text"] = block
    _block_cache["fetched_at"] = now
    return block
