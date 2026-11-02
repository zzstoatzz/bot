"""Review comments reach phi even when jetstream does not deliver them.

2026-08-21: three jetstream failures in one afternoon (a quiet socket, an
instance without the event, a cursor past it) each cost a review comment.
The reviewers' PDSes are the authority; the poll reads them, and the
handled set keeps the two paths from waking her twice for one comment.
"""

import json
from datetime import UTC
from unittest.mock import AsyncMock, Mock

import pytest

from bot.core import review_poll

PHI = "did:plc:phi"
OWNER = "did:plc:owner"
REPO = "did:plc:repo"
KNOT = "https://knot.example"
PULL = f"at://{REPO}/org.tangled.track.ticket/7"
PATCH = f"at://{REPO}/org.tangled.review.patch/bafyround"
TICKETS = {
    PULL: {"author": {"did": PHI}, "targetBranch": "main"},
    f"at://{REPO}/org.tangled.track.ticket/8": {
        "author": {"did": "did:plc:x"},
        "targetBranch": "main",
    },
    f"at://{REPO}/org.tangled.track.ticket/9": {"author": {"did": PHI}},  # an issue
}


def _record(uri_rkey, subject, created="2099-01-01T00:00:00Z", editor=OWNER):
    return {
        "uri": f"at://{REPO}/org.tangled.feed.comment/{uri_rkey}",
        "value": {
            "subject": {"uri": subject, "cid": "bafy"},
            "body": {"text": "2/10"},
            "createdAt": created,
            "x-tngl-editor": editor,
        },
    }


@pytest.fixture
def handled_file(tmp_path, monkeypatch):
    monkeypatch.setattr(review_poll, "HANDLED_FILE", tmp_path / "h.json")
    monkeypatch.setattr(review_poll, "_pds_cache", {REPO: KNOT})
    monkeypatch.setattr(review_poll, "_ticket_authors", {})
    from bot.core import ops_log

    monkeypatch.setattr(ops_log, "WATCHED_CURSOR_FILE", tmp_path / "w.json")
    return tmp_path / "h.json"


def _http(records):
    async def get(url, params, timeout=None):
        if url.endswith("listRecords"):
            assert (params["repo"], params["reverse"]) == (REPO, "true")
            return Mock(text=json.dumps({"records": records}))
        if url.endswith("getTicketView"):
            return Mock(json=Mock(return_value=TICKETS.get(params["uri"], {})))
        assert url == f"{KNOT}/xrpc/com.atproto.repo.getRecord"
        return Mock(json=Mock(return_value={"value": {"ticket": "7"}}))

    http = Mock()
    http.get = AsyncMock(side_effect=get)
    return http


async def _poll(records):
    return await review_poll.new_review_comments(PHI, (OWNER,), _http(records), (REPO,))


async def test_new_comments_on_phis_pulls_only_once(handled_file):
    records = [
        _record("r1", PULL),
        _record("r2", f"at://{REPO}/org.tangled.track.ticket/8"),  # someone's pull
        _record("r3", f"at://{REPO}/org.tangled.track.ticket/9"),  # phi's issue
        _record("r4", PULL, editor="did:plc:stranger"),
    ]
    found = await _poll(records)
    assert [c["uri"] for c in found] == [f"at://{REPO}/org.tangled.feed.comment/r1"]
    assert (found[0]["did"], found[0]["pull"]) == (OWNER, PULL)
    review_poll.mark_handled(found[0]["uri"])
    assert await _poll(records) == []


async def test_a_comment_on_a_round_names_its_pull(handled_file):
    [found] = await _poll([_record("r1", PATCH)])
    assert found["pull"] == PULL


async def test_jetstream_and_poll_share_the_handled_set(handled_file):
    uri = f"at://{REPO}/org.tangled.feed.comment/r1"
    review_poll.mark_handled(uri)
    assert review_poll.was_handled(uri)
    assert await _poll([_record("r1", PULL)]) == []


async def test_old_comments_are_not_replayed_on_a_fresh_start(handled_file):
    assert await _poll([_record("old", PULL, created="2020-01-01T00:00:00Z")]) == []


async def test_comments_the_jetstream_path_already_handled_are_not_rewoken(
    handled_file, tmp_path
):
    """18:45: the first poll woke phi for the 17:13 comment jetstream had
    handled at 17:42 — recorded in the watched cursor, not the handled set."""
    from datetime import datetime

    from bot.core import ops_log

    t = datetime(2099, 1, 1, tzinfo=UTC)
    ops_log._set_watched_cursor(int(t.timestamp() * 1_000_000))
    older = _record("r1", PULL, created=t.isoformat().replace("+00:00", "Z"))
    newer = _record("r2", PULL, created="2099-01-02T00:00:00Z")
    found = await _poll([older, newer])
    assert [c["uri"].rsplit("/", 1)[-1] for c in found] == ["r2"]
