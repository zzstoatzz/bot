"""Every runtime skill directory must load; a malformed frontmatter drops it silently."""

from pathlib import Path

from pydantic_ai_skills import SkillsToolset

SKILLS_DIR = Path(__file__).parent.parent / "skills"


def test_every_skill_directory_loads():
    toolset = SkillsToolset(
        directories=[SKILLS_DIR], exclude_tools=["run_skill_script"]
    )
    loaded = {skill.name: skill for skill in toolset.skills.values()}
    expected = {path.parent.name for path in SKILLS_DIR.glob("*/SKILL.md")}
    assert expected == set(loaded)
    assert all(skill.description for skill in loaded.values())
