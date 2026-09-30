"""Topic labels for Phi's own top-level posts, used by [RECENT OPERATIONS].

A sub-agent names each post's subject so the block can show what she covered
without repeating her sentences. Each text is labelled once: overlapping
renders share the request in flight, and labels persist on the volume so a
restart does not relabel the window.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from pydantic_ai import Agent

from bot.config import settings

logger = logging.getLogger("bot.post_topics")

TOPIC_LABEL_MAX = 120
TOPIC_CACHE_FILE = Path("/data/post_topics.json")
_topic_cache: dict[str, str] | None = None
_inflight: dict[str, asyncio.Task[str]] = {}
_topic_agent: Agent | None = None


def _get_agent() -> Agent:
    global _topic_agent
    if _topic_agent is None:
        _topic_agent = Agent[None, str](
            name="phi-post-topic",
            model=settings.extraction_model,
            system_prompt=(
                "Label the subject of one social media post for a deduplication "
                "index. Output one line of at most twelve words: the concrete "
                "subject, naming the people, projects, places, numbers and events "
                "it is about. Use plain nouns, like a filing label. Do not quote "
                "the post, copy its phrasing, or describe its tone or argument. "
                "No punctuation beyond commas and semicolons."
            ),
            output_type=str,
        )
    return _topic_agent


async def _label_topic(text: str) -> str:
    try:
        result = await _get_agent().run(text)
    except Exception as e:
        logger.warning(f"post topic label failed: {type(e).__name__}: {e}")
        return ""
    label = " ".join((result.output or "").split())
    return label[:TOPIC_LABEL_MAX]


def _load_topics() -> dict[str, str]:
    global _topic_cache
    if _topic_cache is None:
        try:
            _topic_cache = json.loads(TOPIC_CACHE_FILE.read_text())
        except FileNotFoundError:
            _topic_cache = {}
        except (OSError, ValueError) as e:
            logger.warning(f"post topic cache unreadable: {e}")
            _topic_cache = {}
    return _topic_cache


def _save_topics(cache: dict[str, str]) -> None:
    try:
        tmp = TOPIC_CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache))
        tmp.replace(TOPIC_CACHE_FILE)
    except OSError as e:
        logger.warning(f"post topic cache not saved: {e}")


def _label_once(text: str) -> asyncio.Task[str]:
    """One labelling request per post text, shared by overlapping renders."""
    task = _inflight.get(text)
    if task is None:
        task = asyncio.ensure_future(_label_topic(text))
        _inflight[text] = task
        task.add_done_callback(lambda _: _inflight.pop(text, None))
    return task


async def labels_for(texts: set[str]) -> dict[str, str]:
    """Labels for these post texts; texts that fail to label are absent.

    Entries for texts no longer in the window are dropped.
    """
    cache = _load_topics()
    changed = bool(set(cache) - texts)
    for stale in set(cache) - texts:
        del cache[stale]
    pending = sorted(texts - set(cache))
    if pending:
        labels = await asyncio.gather(
            *(asyncio.shield(_label_once(t)) for t in pending)
        )
        for text, label in zip(pending, labels, strict=True):
            if label:
                cache[text] = label
                changed = True
    if changed:
        _save_topics(cache)
    return dict(cache)
