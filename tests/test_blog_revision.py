from types import SimpleNamespace
from unittest.mock import Mock

from bot.tools import blog
from bot.types import GreenGaleDocument


def setup_repo(monkeypatch):
    original = {
        "$type": "app.greengale.document",
        "title": "old",
        "content": "old",
        "publishedAt": "2026-09-07",
        "path": "/abc",
        "url": "https://greengale.app/phi.test",
        "tags": ["old"],
        "custom": "preserved",
    }
    repo = SimpleNamespace(
        get_record=Mock(return_value=SimpleNamespace(cid="v1", value=original)),
        put_record=Mock(),
    )
    monkeypatch.setattr(
        blog.bot_client,
        "client",
        SimpleNamespace(com=SimpleNamespace(atproto=SimpleNamespace(repo=repo))),
    )
    return repo, original


def test_revision_preserves_publication_identity_and_uses_cas(monkeypatch):
    repo, original = setup_repo(monkeypatch)
    doc = GreenGaleDocument(title="corrected", content="corrected body")
    result = blog._revise_blog_document(
        "did:plc:phi",
        "phi.test",
        "at://did:plc:phi/app.greengale.document/abc",
        "v1",
        doc,
        None,
    )
    assert result == "updated: https://greengale.app/phi.test/abc"
    data = repo.put_record.call_args.kwargs["data"]
    assert data["swap_record"] == "v1"
    assert data["record"] == {
        **original,
        "title": "corrected",
        "content": "corrected body",
    }


def test_stale_revision_refuses_write(monkeypatch):
    repo, _ = setup_repo(monkeypatch)
    result = blog._revise_blog_document(
        "did:plc:phi",
        "phi.test",
        "at://did:plc:phi/app.greengale.document/abc",
        "v0",
        GreenGaleDocument(title="new", content="body"),
        [],
    )
    assert "changed since" in result
    repo.put_record.assert_not_called()


def test_foreign_revision_refuses_read_and_write(monkeypatch):
    repo, _ = setup_repo(monkeypatch)
    result = blog._revise_blog_document(
        "did:plc:phi",
        "phi.test",
        "at://did:plc:other/app.greengale.document/abc",
        "v1",
        GreenGaleDocument(title="new", content="body"),
        [],
    )
    assert "own repo" in result
    repo.get_record.assert_not_called()
    repo.put_record.assert_not_called()


async def test_registered_revision_rejection_prevents_write(monkeypatch):
    from unittest.mock import AsyncMock

    registered = {}
    blog.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    monkeypatch.setattr(blog, "get_override", AsyncMock(return_value={"active": False}))
    gate = AsyncMock(return_value=("rejected", ""))
    monkeypatch.setattr(blog, "_policy_gate", gate)
    auth = AsyncMock()
    monkeypatch.setattr(blog.bot_client, "authenticate", auth)
    result = await registered["publish_blog_post"](
        SimpleNamespace(deps=None),
        "new title",
        "complete corrected body",
        uri="at://did:plc:phi/app.greengale.document/abc",
        expected_cid="v1",
    )
    assert result == "rejected"
    assert "complete corrected body" in gate.call_args.args[0]
    auth.assert_not_awaited()


def test_revision_cas_failure_does_not_report_success(monkeypatch):
    import pytest

    repo, _ = setup_repo(monkeypatch)
    repo.put_record.side_effect = RuntimeError("InvalidSwap")
    with pytest.raises(RuntimeError, match="InvalidSwap"):
        blog._revise_blog_document(
            "did:plc:phi",
            "phi.test",
            "at://did:plc:phi/app.greengale.document/abc",
            "v1",
            GreenGaleDocument(title="new", content="body"),
            [],
        )
