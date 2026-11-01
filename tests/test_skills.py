"""Every runtime skill directory must load; a malformed frontmatter drops it silently."""

from pathlib import Path

from pydantic_ai_skills import SkillsCapability
from pydantic_ai_skills._parsing import read_skill_info

SKILLS_DIR = Path(__file__).parent.parent / "skills"


def test_every_skill_directory_loads():
    expected = {path.parent.name for path in SKILLS_DIR.glob("*/SKILL.md")}
    assert set(SkillsCapability(SKILLS_DIR, scripts=False).skill_names) == expected
    infos = [read_skill_info(SKILLS_DIR / name) for name in expected]
    assert all(info and info.description for info in infos)
