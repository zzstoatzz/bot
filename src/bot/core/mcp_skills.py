"""Skills that MCP servers publish as `skill://` resources, read into phi's catalog.

A FastMCP skills provider lists each skill's `SKILL.md` and a `_manifest` of
its files with sizes and sha256 digests. This reads them through the same
MCP client phi's toolsets use and keeps a skill only when every file matches
its manifest entry. The standard `skills/list` request needs the FastMCP 4
client, which pydantic-ai 1.x cannot share an environment with; the
manifest resource is FastMCP's documented fallback for exactly that client.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Protocol

from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.messages import BinaryContent
from pydantic_ai_skills import Skill, SkillResource
from pydantic_ai_skills.directory import parse_skill_md
from pydantic_ai_skills.exceptions import SkillNotFoundError
from pydantic_ai_skills.registries import SkillRegistry

logger = logging.getLogger("bot.mcp_skills")

MAIN_FILE = "SKILL.md"


class SkillMismatch(Exception):
    """A served file differs from its manifest entry."""


def _skill_paths(uris: list[str]) -> list[str]:
    """`skill://atproto-docs/SKILL.md` → `atproto-docs`, for each listed skill."""
    suffix = f"/{MAIN_FILE}"
    return sorted(
        uri.removeprefix("skill://").removesuffix(suffix)
        for uri in uris
        if uri.startswith("skill://") and uri.endswith(suffix)
    )


def _as_bytes(content: object) -> bytes:
    if isinstance(content, str):
        return content.encode()
    if isinstance(content, BinaryContent):
        return content.data
    raise SkillMismatch(f"unexpected resource content {type(content).__name__}")


def _verified(entry: dict, data: bytes) -> bytes:
    if len(data) != entry["size"]:
        raise SkillMismatch(
            f"{entry['path']}: {len(data)} bytes, manifest says {entry['size']}"
        )
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    if digest != entry["hash"]:
        raise SkillMismatch(f"{entry['path']}: digest differs from manifest")
    return data


class ResourceReader(Protocol):
    async def read_resource(self, uri: str) -> object: ...


async def read_skill(server: ResourceReader, path: str, source: str) -> Skill:
    """Read one skill and every file its manifest lists, verifying each."""
    manifest = json.loads(
        _as_bytes(await server.read_resource(f"skill://{path}/_manifest"))
    )
    files: dict[str, bytes] = {}
    for entry in manifest["files"]:
        data = await server.read_resource(f"skill://{path}/{entry['path']}")
        files[entry["path"]] = _verified(entry, _as_bytes(data))
    if MAIN_FILE not in files:
        raise SkillMismatch(f"{path}: manifest has no {MAIN_FILE}")
    frontmatter, body = parse_skill_md(files.pop(MAIN_FILE).decode())
    name = frontmatter.get("name") or Path(path).name
    if name != Path(path).name or not frontmatter.get("description"):
        raise SkillMismatch(
            f"{path}: frontmatter needs a matching name and a description"
        )
    return Skill(
        name=name,
        description=frontmatter["description"],
        content=body,
        resources=[
            SkillResource(name=file, content=data.decode())
            for file, data in sorted(files.items())
        ],
        uri=f"skill://{path}",
        metadata={"source": source},
    )


async def fetch_skills(url: str) -> list[Skill]:
    """Every verifiable skill a server lists; a bad skill is skipped, not fatal."""
    server = MCPServerStreamableHTTP(url=url, timeout=30)
    skills = []
    async with server:
        resources = await server.list_resources()
        for path in _skill_paths([str(r.uri) for r in resources]):
            try:
                skills.append(await read_skill(server, path, url))
            except (SkillMismatch, KeyError, ValueError, UnicodeDecodeError) as e:
                logger.warning(f"skipping skill {path} from {url}: {e}")
    return skills


class MCPSkillsRegistry(SkillRegistry):
    """Skills from MCP servers, cached; `refresh()` re-reads them."""

    def __init__(self, urls: list[str]) -> None:
        self.urls = urls
        self._skills: list[Skill] = []

    async def refresh(self) -> list[Skill]:
        skills = []
        for url in self.urls:
            try:
                skills.extend(await fetch_skills(url))
            except Exception as e:
                logger.warning(f"skills from {url} unavailable: {e}")
        self._skills = skills
        return skills

    def get_skills(self) -> list[Skill]:
        return list(self._skills)

    async def search(self, query: str, limit: int = 10) -> list[Skill]:
        q = query.lower()
        return [
            s for s in self._skills if q in s.name.lower() or q in s.description.lower()
        ][:limit]

    async def get(self, skill_name: str) -> Skill:
        for skill in self._skills:
            if skill.name == skill_name:
                return skill
        raise SkillNotFoundError(skill_name)

    async def install(self, skill_name: str, target_dir: str | Path) -> Path:
        raise NotImplementedError("MCP skills are read in place, not installed")

    async def update(self, skill_name: str, target_dir: str | Path) -> Path:
        raise NotImplementedError("MCP skills are read in place, not installed")
