"""Skills that MCP servers publish, synced into a local library for phi's catalog.

`SkillsCapability` reads skill libraries from disk. This registry fills one
from MCP servers through the Skills extension (SEP-2640): `skills/list`
names each skill, and FastMCP's `read_skill` fetches every file and checks
it against the server's size and sha256 manifest before anything is written.
"""

import asyncio
import logging
import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastmcp import Client, FastMCP
from fastmcp.skills import SkillsClientExtension
from pydantic_ai_skills import SkillRegistry

logger = logging.getLogger("bot.mcp_skills")


async def sync_server(url: str | FastMCP, library: Path) -> list[str]:
    """Write each verifiable skill `url` lists into `library`; skip the rest."""
    written = []
    async with Client(
        url, mode="auto", extensions=[SkillsClientExtension()], timeout=30
    ) as client:
        for entry in await client.list_skills():
            try:
                skill = await client.read_skill(entry.uri)
                skill.to_directory(library / skill.name, overwrite=True)
                written.append(skill.name)
            except Exception as e:
                logger.warning(f"skipping skill {entry.uri} from {url}: {e}")
    return written


class MCPSkillsRegistry(SkillRegistry):
    """A per-process library of the skills `urls` serve."""

    def __init__(
        self, urls: Sequence[str | FastMCP], library: Path | None = None
    ) -> None:
        self.urls = urls
        self.library = library or Path(tempfile.mkdtemp(prefix="phi-mcp-skills-"))
        self.synced: list[str] = []

    async def _sync(self) -> None:
        self.synced = []
        for url in self.urls:
            try:
                self.synced += await sync_server(url, self.library)
            except Exception as e:
                logger.warning(f"skills from {url} unavailable: {e}")

    def sync(self) -> Path:
        # SkillsCapability calls this from __init__, which can run inside the
        # server's event loop, so the fetch gets a loop of its own.
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, self._sync()).result()
        logger.info(f"remote skills: {sorted(self.synced)}")
        return self.library
