"""Skills MCP servers publish join phi's catalog only as verified files."""

from pathlib import Path

from fastmcp import Client, FastMCP, Skill
from fastmcp.skills.provider import SkillCatalogProvider
from pydantic_ai_skills import SkillsCapability

from bot.core.mcp_skills import MCPSkillsRegistry

DOCS = Skill(
    name="atproto-docs",
    description="Answer AT Protocol questions from atproto.com.",
    instructions="# atproto docs\n\nCall `search_atproto_docs`.\n",
    files={"kinds.md": "specs, guides, blog\n"},
)


def _server(*skills: Skill) -> FastMCP:
    mcp = FastMCP("docs")
    mcp.add_provider(SkillCatalogProvider(list(skills)))
    return mcp


def test_listed_skills_are_written_with_their_files(tmp_path):
    registry = MCPSkillsRegistry([_server(DOCS)], library=tmp_path)
    library = registry.sync()
    assert registry.synced == ["atproto-docs"]
    assert (
        library / "atproto-docs" / "kinds.md"
    ).read_text() == "specs, guides, blog\n"
    assert "search_atproto_docs" in (library / "atproto-docs" / "SKILL.md").read_text()


def test_remote_skills_join_the_catalog_and_local_ones_win(tmp_path):
    local = tmp_path / "local"
    (local / "read-thread").mkdir(parents=True)
    (local / "read-thread" / "SKILL.md").write_text(
        "---\nname: read-thread\ndescription: the local one\n---\nlocal body\n"
    )
    shadow = Skill(name="read-thread", description="the remote one", instructions="x\n")
    registry = MCPSkillsRegistry([_server(DOCS, shadow)], library=tmp_path / "remote")
    capability = SkillsCapability(
        local,
        registries=[registry.filtered(lambda info: info.name != "read-thread")],
        scripts=False,
    )
    assert capability.skill_names == ["atproto-docs", "read-thread"]


def test_a_skill_that_fails_verification_is_skipped(tmp_path, monkeypatch):
    other = Skill(name="other", description="Another skill.", instructions="y\n")
    real = Client.read_skill

    async def read_skill(self, uri, **kwargs):
        if "atproto-docs" in uri:
            raise ValueError("kinds.md does not match the manifest digest")
        return await real(self, uri, **kwargs)

    monkeypatch.setattr(Client, "read_skill", read_skill)
    registry = MCPSkillsRegistry([_server(DOCS, other)], library=tmp_path)
    registry.sync()
    assert registry.synced == ["other"]
    assert not (tmp_path / "atproto-docs").exists()


def test_an_unreachable_server_leaves_an_empty_library(tmp_path):
    registry = MCPSkillsRegistry(["http://127.0.0.1:9/mcp"], library=tmp_path)
    assert registry.sync() == tmp_path
    assert registry.synced == []
    assert list(Path(tmp_path).iterdir()) == []
