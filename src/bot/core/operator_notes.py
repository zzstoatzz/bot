"""[OPERATOR NOTES] — the titles of the operator's working notes.

The operator-notes skill has been in the catalog since it was written and
went unloaded for 267 runs (docs/toolset-audit-2026-10.md): a one-line
catalog entry names subjects, and a subject list does not tell phi that the
thing in front of her has already been worked out. The titles do.

Titles only. Reading a note is the skill's job.
"""

import logging
import re
import time

import httpx

logger = logging.getLogger("bot.operator_notes")

INDEX_URL = "https://notes.zzstoatzz.io/llms.txt"
HEADER = (
    "[OPERATOR NOTES — titles of nate's working notes at notes.zzstoatzz.io, "
    "by section. a map of what he has already worked out, not findings. "
    "the operator-notes skill reads one.]"
)

_BLOCK_TTL_SECONDS = 3600
_block_cache: dict = {"text": "", "fetched_at": 0.0}
_TITLE = re.compile(r"^- \[(.+?)\]\(")


def _render(index: str) -> str:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in index.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
        elif current and (match := _TITLE.match(line)):
            sections.setdefault(current, []).append(match.group(1))
    if not sections:
        return ""
    return "\n".join(
        [HEADER, *(f"{name}: {'; '.join(titles)}" for name, titles in sections.items())]
    )


async def get_operator_notes_block() -> str:
    """Fetch + render the block. A failed refresh keeps the last good index."""
    now = time.time()
    if _block_cache["text"] and now - _block_cache["fetched_at"] < _BLOCK_TTL_SECONDS:
        return _block_cache["text"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(INDEX_URL)
            response.raise_for_status()
        block = _render(response.text)
    except Exception as e:
        logger.warning(f"operator notes index unavailable: {e}")
        return _block_cache["text"]
    if not block:
        logger.warning("operator notes index parsed to no titles")
        return _block_cache["text"]
    _block_cache["text"] = block
    _block_cache["fetched_at"] = now
    return block
