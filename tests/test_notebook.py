import random
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from bot.config import settings
from bot.memory import notebook
from bot.tools import notebook as notebook_tools
from bot.tools._helpers import PhiDeps


@pytest.fixture(autouse=True)
def notebook_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "memory_notebook_path", str(tmp_path / "memory.sqlite3")
    )


def test_revisions_keep_original_evidence():
    original = "Asked about the river. at://alice/app.bsky.feed.post/first"
    notebook.write_page("people/alice", original, 0)
    notebook.write_page(
        "people/alice", "Answered: at://phi/app.bsky.feed.post/reply", 1
    )
    assert notebook.read_page("people/alice", 1)["page"]["content"] == original
    assert notebook.read_page("people/alice")["page"]["revision"] == 2
    assert notebook.read_page("people/alice", 9)["status"] == "not_found"


def test_concurrent_edits_do_not_overwrite_each_other():
    notebook.write_page("index", "first", 0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda text: notebook.write_page("index", text, 1), ["a", "b"])
        )
    assert sorted(r["status"] for r in results) == ["conflict", "ok"]
    assert notebook.read_page("index")["page"]["revision"] == 2
    assert notebook.read_page("index", 1)["page"]["content"] == "first"


def test_generated_stale_edits_preserve_every_accepted_revision():
    rng = random.Random(20261116)
    history: dict[str, list[str]] = {}
    for step in range(250):
        name = rng.choice(["index", "people/a", "questions/b"])
        revisions = history.setdefault(name, [])
        expected_revision = rng.randrange(len(revisions) + 2)
        content = f"record {step}"
        result = notebook.write_page(name, content, expected_revision)
        if expected_revision == len(revisions):
            assert result["status"] == "ok"
            revisions.append(content)
        else:
            assert result["status"] == "conflict"
        current = notebook.read_page(name)["page"]
        assert (current["content"] if current else None) == (
            revisions[-1] if revisions else None
        )
        for revision, text in enumerate(revisions, 1):
            assert notebook.read_page(name, revision)["page"]["content"] == text


def test_index_limit_rejects_without_clipping_or_replacing():
    notebook.write_page("index", "read people/alice", 0)
    with pytest.raises(ValueError, match="exceeds"):
        notebook.write_page("index", "x" * (notebook.INDEX_LIMIT + 1), 1)
    assert notebook.read_page("index")["page"]["content"] == "read people/alice"


def test_search_paginates_current_pages_and_treats_query_literally():
    for name in ["a", "b", "c"]:
        notebook.write_page(name, "needle", 0)
    notebook.write_page("a", "replaced", 1)
    first = notebook.find_pages("needle", limit=1)
    assert [p["name"] for p in first["pages"]] == ["b"]
    assert first["next_after"] == "b"
    second = notebook.find_pages("needle", first["next_after"], limit=1)
    assert [p["name"] for p in second["pages"]] == ["c"]
    assert second["next_after"] is None
    assert notebook.find_pages("%_")["pages"] == []


def test_archiving_preserves_history():
    notebook.write_page("old", "a settled question", 0)
    notebook.write_page("old", "", 1)
    assert notebook.find_pages()["pages"] == []
    assert notebook.read_page("old", 1)["page"]["content"] == "a settled question"


def test_orientation_distinguishes_absence_and_failure(monkeypatch):
    assert "No index yet" in notebook.orientation()
    notebook.write_page("index", "Check the river source", 0)
    assert "Check the river source" in notebook.orientation()

    def broken(*args):
        raise OSError("storage offline")

    monkeypatch.setattr(notebook, "read_page", broken)
    block = notebook.orientation()
    assert "unavailable" in block
    assert "No index yet" not in block


@pytest.fixture
def tools():
    registered = {}

    def tool(fn):
        registered[fn.__name__] = fn
        return fn

    notebook_tools.register(SimpleNamespace(tool=tool))
    return registered


async def test_tool_requires_current_read_and_refuses_stale_edits(tools):
    ctx = SimpleNamespace(deps=PhiDeps(author_handle="alice"))
    write = tools["write_notebook"]
    assert '"status": "ok"' in await write(ctx, "index", "new", 0)
    other = SimpleNamespace(deps=PhiDeps(author_handle="alice"))
    assert '"status": "conflict"' in await write(other, "index", "overwrite", 0)
    assert "Read this page" in await write(other, "index", "overwrite", 1)
    notebook.write_page("index", "another run", 1)
    assert '"status": "conflict"' in await write(ctx, "index", "stale", 1)
    assert notebook.read_page("index")["page"]["content"] == "another run"


async def test_private_runs_can_read_but_cannot_write_shared_pages(tools):
    notebook.write_page("index", "public-source notes", 0)
    ctx = SimpleNamespace(
        deps=PhiDeps(
            author_handle="operator", private_message_context="private decision"
        )
    )
    assert "public-source notes" in await tools["read_notebook"](ctx, "index")
    assert "Not written" in await tools["write_notebook"](
        ctx, "index", "private decision", 1
    )
    assert notebook.read_page("index")["page"]["content"] == "public-source notes"


async def test_historical_read_does_not_authorize_write(tools):
    notebook.write_page("index", "first", 0)
    ctx = SimpleNamespace(deps=PhiDeps(author_handle="alice"))
    await tools["read_notebook"](ctx, "index", revision=1)
    assert "Read this page" in await tools["write_notebook"](ctx, "index", "second", 1)
