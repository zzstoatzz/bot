import os

import pytest

from bot.memory.extraction import (
    get_reconciliation_agent,
    reconciliation_prompt,
    reconciliation_targets,
)


def _rows(*contents: tuple[str, list[str]]) -> list[dict]:
    return [
        {"id": f"row-{n}", "content": content, "tags": tags}
        for n, (content, tags) in enumerate(contents, start=1)
    ]


CASES = [
    pytest.param(
        _rows(
            ("works on a rust crate for async signal handling", ["rust"]),
            ("lives in chicago", ["location"]),
            ("has a dog named biscuit", ["pets"]),
        ),
        ("moved from chicago to denver last month", ["location"]),
        {"UPDATE", "DELETE"},
        {"row-2"},
        id="contradicts the second neighbour only",
    ),
    pytest.param(
        _rows(
            ("uses postgres for the indexer", ["databases"]),
            ("plays bass in a band", ["music"]),
            ("the indexer is backed by postgres on fly", ["databases"]),
        ),
        ("migrated the indexer off postgres to turso", ["databases"]),
        {"UPDATE", "DELETE"},
        {"row-1", "row-3"},
        id="contradicts the first and third",
    ),
    pytest.param(
        _rows(
            ("writes zig for a typeahead service", ["zig"]),
            ("runs a relay on a home server", ["infrastructure"]),
            ("dislikes yaml", ["tooling"]),
        ),
        ("is learning to bake sourdough", ["food"]),
        {"ADD"},
        set(),
        id="unrelated to every neighbour",
    ),
    pytest.param(
        _rows(
            ("maintains an atproto python sdk", ["atproto"]),
            ("is interested in atproto feed generators", ["atproto"]),
            ("thinks lexicons should be versioned", ["atproto"]),
        ),
        ("built a labeler for atproto last week", ["atproto"]),
        {"ADD"},
        set(),
        id="same topic as all three, restates none",
    ),
    pytest.param(
        _rows(
            (
                "integrated lake point tower webcam for northern chicago shoreline views",
                ["webcams"],
            ),
        ),
        (
            "integrated edgewater lakeshore highrise webcam providing southern views "
            "over osterman beach toward chicago loop",
            ["webcams"],
        ),
        {"ADD"},
        set(),
        id="a second thing of the same kind",
    ),
    pytest.param(
        _rows(
            (
                "created @chef.cee.wtf, a tool that analyzes bluesky post engagement "
                "by labeler",
                ["tools"],
            ),
            ("has strong aesthetic preferences for teal and orange", ["aesthetics"]),
        ),
        (
            "created rite.mino.mobi/sharp, a tool for cycling through single-syllable "
            "english words with an obscurity filter",
            ["tools"],
        ),
        {"ADD"},
        set(),
        id="a second tool by the same person",
    ),
    pytest.param(
        _rows(
            ("prefers vim", ["tooling"]),
            ("works at a workflow orchestration company", ["work"]),
            ("has a dog named biscuit", ["pets"]),
        ),
        ("owns a dog called biscuit", ["pets"]),
        {"NOOP"},
        {"row-3"},
        id="restates the third neighbour",
    ),
]


@pytest.fixture(autouse=True)
def openai_key(settings):
    if not settings.openai_api_key:
        raise pytest.skip.Exception("Requires OPENAI_API_KEY")
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)


@pytest.mark.parametrize(("existing", "new", "actions", "superseded"), CASES)
async def test_live_reconciler_names_the_rows_it_means(
    existing, new, actions, superseded
):
    content, tags = new
    result = await get_reconciliation_agent().run(
        reconciliation_prompt(existing, content, tags)
    )
    decision = result.output.decision
    action = decision.action.upper()
    assert action in actions, decision

    if action in ("UPDATE", "DELETE"):
        named = {row["id"] for row in reconciliation_targets(decision, existing)}
        assert named == superseded, decision
    elif action == "ADD":
        assert decision.targets == [], decision
    else:
        assert {f"row-{n}" for n in decision.targets} == superseded, decision
