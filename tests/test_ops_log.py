"""Ops log: jetstream events → durable rows → [RECENT OPERATIONS].

The regression these tests guard: [RECENT OPERATIONS] used to be a
listRecords snapshot bounded by TOP_N=10 rows — deletes were invisible,
edits looked like creates, and on a busy day the "window" was a few hours,
which is how phi re-posted a 24h-old subject verbatim (gracekind,
2026-08-05/06 22:02).
"""

import json
import time
from pathlib import Path

import pytest

from bot.core import ops_log
from bot.core.recent_operations import _merge, _render, _Row, _rows_from_ops


@pytest.fixture(autouse=True)
def _tmp_log(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ops_log.settings, "ops_log_path", str(tmp_path / "ops_log.jsonl")
    )
    ops_log._local_writes.clear()


def _event(
    op, nsid="app.bsky.feed.post", rkey="3abc", record=None, time_us=None, rev="r"
):
    return {
        "did": "did:plc:x",
        "kind": "commit",
        "time_us": time_us or int(time.time() * 1_000_000),
        "commit": {
            "rev": rev,
            "operation": op,
            "collection": nsid,
            "rkey": rkey,
            **({"record": record} if record is not None else {}),
        },
    }


def test_event_to_row_create_keeps_post_record():
    row = ops_log.event_to_row(_event("create", record={"text": "hi"}))
    assert row is not None
    assert row["op"] == "create"
    assert row["record"] == {"text": "hi"}


def test_event_to_row_drops_bodies_for_noise_collections():
    row = ops_log.event_to_row(
        _event("create", nsid="app.bsky.feed.like", record={"subject": {}})
    )
    assert row is not None
    assert row["record"] is None


def test_event_to_row_ignores_non_commit():
    assert ops_log.event_to_row({"kind": "identity"}) is None


def test_append_read_window_and_cursor():
    old = ops_log.event_to_row(
        _event(
            "create",
            rkey="3old",
            record={"text": "old"},
            time_us=int((time.time() - 72 * 3600) * 1_000_000),
        )
    )
    new = ops_log.event_to_row(_event("create", rkey="3new", record={"text": "new"}))
    assert old and new
    ops_log.append_op(old)
    ops_log.append_op(new)
    rows = ops_log.read_ops(window_hours=48)
    assert [r["rkey"] for r in rows] == ["3new"]
    assert ops_log.last_cursor_us() == new["time_us"]


def test_read_ops_tolerates_torn_tail_write():
    row = ops_log.event_to_row(_event("create", record={"text": "ok"}))
    assert row
    ops_log.append_op(row)
    with open(ops_log.settings.ops_log_path, "a") as f:
        f.write('{"time_us": 123, "truncat')
    assert [r["rkey"] for r in ops_log.read_ops(48)] == ["3abc"]


def test_prune_drops_expired_rows():
    ancient = ops_log.event_to_row(
        _event(
            "create",
            rkey="3anc",
            record={"text": "x"},
            time_us=int((time.time() - 30 * 86400) * 1_000_000),
        )
    )
    fresh = ops_log.event_to_row(_event("create", rkey="3fresh", record={"text": "y"}))
    assert ancient and fresh
    ops_log.append_op(ancient)
    ops_log.append_op(fresh)
    ops_log.prune_log()
    content = Path(ops_log.settings.ops_log_path).read_text()
    assert "3fresh" in content and "3anc" not in content


def test_local_write_attribution():
    ops_log.record_local_write("at://did:plc:x/app.bsky.feed.post/3abc")
    row = ops_log.event_to_row(_event("create", record={"text": "mine"}))
    assert row and row["local"] is True
    other = ops_log.event_to_row(_event("delete", rkey="3zzz"))
    assert other and other["local"] is False


# --- delete visibility through [RECENT OPERATIONS] ---


def _op(op, rkey, nsid="network.cosmik.card", record=None, offset_s=0):
    t = int((time.time() + offset_s) * 1_000_000)
    return ops_log.OpRow(
        time_us=t,
        at=ops_log._iso_from_us(t),
        op=op,
        nsid=nsid,
        rkey=rkey,
        local=False,
        record=record,
        rev=f"rev-{rkey}-{op}-{t}",
    )


def test_replayed_commit_from_another_instance_reads_once():
    """time_us is the jetstream instance's clock, not the commit's: a
    rotation to another instance re-emits the same commit under a new
    stamp, and the 2026-09-02 log held one post 352 times. the commit
    rev is what identifies a write."""
    base = int(time.time() * 1_000_000)
    first = ops_log.event_to_row(
        _event("create", record={"text": "once"}, time_us=base, rev="rev1")
    )
    replay = ops_log.event_to_row(
        _event("create", record={"text": "once"}, time_us=base + 4_281, rev="rev1")
    )
    assert first and replay
    ops_log.append_op(first)
    ops_log.append_op(replay)
    rows = ops_log.read_ops(48)
    assert len(rows) == 1


def test_distinct_revs_on_one_rkey_stay_distinct():
    base = int(time.time() * 1_000_000)
    a = ops_log.event_to_row(
        _event(
            "update",
            nsid="io.zzstoatzz.phi.goal",
            rkey="self",
            record={"n": 1},
            time_us=base,
            rev="a",
        )
    )
    b = ops_log.event_to_row(
        _event(
            "update",
            nsid="io.zzstoatzz.phi.goal",
            rkey="self",
            record={"n": 2},
            time_us=base + 1,
            rev="b",
        )
    )
    assert a and b
    ops_log.append_op(a)
    ops_log.append_op(b)
    assert len(ops_log.read_ops(48)) == 2


def test_legacy_rows_without_rev_collapse_on_identical_body():
    base = int(time.time() * 1_000_000)
    with open(ops_log.settings.ops_log_path, "a") as f:
        f.writelines(
            json.dumps(
                {
                    "time_us": base + offset,
                    "at": ops_log._iso_from_us(base + offset),
                    "op": "create",
                    "nsid": "app.bsky.feed.post",
                    "rkey": "3legacy",
                    "local": False,
                    "record": {"text": "same"},
                }
            )
            + "\n"
            for offset in (0, 5_000)
        )
    assert len(ops_log.read_ops(48)) == 1


def test_external_delete_is_visible_and_flagged():
    """The semble tripwire: an external service deleting phi's cards must
    show up, attributed as not-this-process — the old snapshot rendered
    nothing at all for a delete."""
    rows = _rows_from_ops(
        [
            _op("create", "3card", record={"type": "NOTE"}),
            _op("delete", "3card", offset_s=60),
        ]
    )
    block = _render(rows, repo="did:plc:phi")
    assert "DELETED (not via this process)" in block
    assert "was: NOTE card" in block  # phi sees WHAT vanished
    assert "at://did:plc:phi/network.cosmik.card/3card" in block


def test_edit_renders_as_edit():
    rows = _rows_from_ops(
        [
            _op(
                "update",
                "3p",
                nsid="app.bsky.feed.post",
                record={"text": "second thoughts"},
            )
        ]
    )
    assert "EDITED" in _render(rows)


def test_merge_prefers_event_rows_and_backfills_snapshot():
    event_rows = _rows_from_ops(
        [_op("create", "3a", nsid="app.bsky.feed.post", record={"text": "live"})]
    )
    snapshot: list[_Row] = [
        {
            "rkey": "3a",
            "nsid": "app.bsky.feed.post",
            "created_at": "2026-08-06T00:00:00",
            "summary": "stale",
            "op": "create",
            "local": False,
        },
        {
            "rkey": "3b",
            "nsid": "app.bsky.feed.post",
            "created_at": "2026-08-06T00:00:01",
            "summary": "gap-fill",
            "op": "create",
            "local": False,
        },
    ]
    merged = _merge(event_rows, snapshot)  # type: ignore[arg-type]
    summaries = [r["summary"] for r in merged]
    assert "gap-fill" in summaries
    assert "stale" not in summaries


def test_window_announces_truncation():
    rows = _rows_from_ops(
        [
            _op(
                "create",
                f"3r{i}",
                nsid="app.bsky.feed.post",
                record={"text": str(i)},
                offset_s=i,
            )
            for i in range(5)
        ]
    )
    block = _render(rows[-3:], truncated=2)
    assert "2 older rows elided" in block


def test_op_rows_roundtrip_through_jsonl():
    row = ops_log.event_to_row(_event("create", record={"text": "persist me"}))
    assert row
    ops_log.append_op(row)
    line = Path(ops_log.settings.ops_log_path).read_text().strip()
    assert json.loads(line) == row


def test_read_ops_dedupes_reconnect_replays():
    """The consumer rewinds the cursor 5s on reconnect; replayed appends
    must collapse to one row."""
    row = ops_log.event_to_row(_event("create", record={"text": "once"}))
    assert row
    ops_log.append_op(row)
    ops_log.append_op(row)
    assert len(ops_log.read_ops(48)) == 1


def test_compact_collapses_reply_runs_and_card_pairs(monkeypatch):
    """2026-08-07 diet: consecutive replies rendered one row each and every
    semble save billed two rows (URL card + NOTE card written together)."""
    # Keep the pair in the same calendar minute regardless of test start time.
    base = int(time.time() // 60) * 60
    monkeypatch.setattr(time, "time", lambda: base)
    rows = _rows_from_ops(
        [
            _op(
                "create",
                "3r1",
                nsid="app.bsky.feed.post",
                record={"text": "a" * 50, "reply": {"parent": {}}},
            ),
            _op(
                "create",
                "3r2",
                nsid="app.bsky.feed.post",
                record={"text": "b" * 30, "reply": {"parent": {}}},
                offset_s=10,
            ),
            _op(
                "create",
                "3r3",
                nsid="app.bsky.feed.post",
                record={"text": "c" * 20, "reply": {"parent": {}}},
                offset_s=20,
            ),
            _op(
                "create",
                "3c1",
                nsid="network.cosmik.card",
                record={"type": "URL", "content": {"title": "some page"}},
                offset_s=30,
            ),
            _op(
                "create",
                "3c2",
                nsid="network.cosmik.card",
                record={"type": "NOTE"},
                offset_s=31,
            ),
        ]
    )
    block = _render(rows)
    assert "replies ×3" in block
    assert "reply (50 chars)" not in block
    assert "+note" in block
    assert block.count("network.cosmik.card") == 1


def test_compact_leaves_top_level_posts_alone():
    rows = _rows_from_ops(
        [
            _op("create", "3p1", nsid="app.bsky.feed.post", record={"text": "one"}),
            _op(
                "create",
                "3p2",
                nsid="app.bsky.feed.post",
                record={"text": "two"},
                offset_s=5,
            ),
        ]
    )
    block = _render(rows)
    assert '"one"' in block and '"two"' in block


def test_routine_writes_tally_instead_of_row_per_write():
    """2026-08-15 audit: [RECENT OPERATIONS] averaged 10-14k chars, ~1/3 of
    every prompt, mostly one-row-per-reply/like/goal-write. Routine activity
    tallies to one line; content rows stay individual."""
    rows = _rows_from_ops(
        [
            _op(
                "create", "3p", nsid="app.bsky.feed.post", record={"text": "kept whole"}
            ),
            _op(
                "update",
                "3g1",
                nsid="io.zzstoatzz.phi.goal",
                record={
                    "title": "make 3 friends",
                    "created_at": "a",
                    "updated_at": "b",
                },
                offset_s=10,
            ),
            _op(
                "update",
                "3g1",
                nsid="io.zzstoatzz.phi.goal",
                record={
                    "title": "make 3 friends",
                    "created_at": "a",
                    "updated_at": "c",
                },
                offset_s=20,
            ),
            _op(
                "create",
                "3l",
                nsid="app.bsky.feed.like",
                record={"subject": {"uri": "at://x"}},
                offset_s=30,
            ),
        ]
    )
    for r in rows:
        r["local"] = True
    block = _render(rows)
    assert '"kept whole"' in block
    assert "goal updates ×2" in block
    assert "likes ×1" in block
    assert "goal updated" not in block  # no per-write goal rows
    assert block.count("routine (") == 1


def test_anomalies_never_tally():
    """Deletes and external edits stay row-level — the tamper channel."""
    rows = _rows_from_ops(
        [
            _op(
                "create",
                "3l",
                nsid="app.bsky.feed.like",
                record={"subject": {"uri": "at://x"}},
            ),
            _op("delete", "3l", nsid="app.bsky.feed.like", offset_s=5),
            _op(
                "update",
                "3g",
                nsid="io.zzstoatzz.phi.goal",
                record={"title": "t", "created_at": "a", "updated_at": "b"},
                offset_s=10,
            ),
        ]
    )
    block = _render(rows)  # local=False: external edit must not tally
    assert "DELETED (not via this process)" in block
    assert "EDITED (not via this process)" in block
    assert "likes ×1" in block


class TestResumeCursor:
    def test_read_position_wins_when_older_than_her_last_op(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(ops_log, "STREAM_CURSOR_FILE", tmp_path / "s.json")
        monkeypatch.setattr(ops_log, "last_cursor_us", lambda: 8_34_00)
        ops_log._set_stream_cursor(8_20_00)
        assert ops_log.resume_cursor_us() == 8_20_00

    def test_first_run_rewinds_an_hour_from_her_last_op(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ops_log, "STREAM_CURSOR_FILE", tmp_path / "missing.json")
        monkeypatch.setattr(ops_log, "last_cursor_us", lambda: 10 * 60 * 60 * 1_000_000)
        assert ops_log.resume_cursor_us() == 9 * 60 * 60 * 1_000_000

    async def test_other_repository_cannot_advance_the_read_position(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(ops_log, "STREAM_CURSOR_FILE", tmp_path / "s.json")
        appended = []
        monkeypatch.setattr(ops_log, "append_op", appended.append)
        consumer = ops_log.OpsLogConsumer("did:plc:phi")
        await consumer._handle(
            json.dumps(
                {
                    "did": "did:plc:reviewer",
                    "kind": "commit",
                    "time_us": 5_000_000,
                    "commit": {
                        "operation": "create",
                        "collection": "org.tangled.feed.comment",
                        "rkey": "review",
                    },
                }
            )
        )
        assert appended == []
        assert ops_log._stream_cursor() == 0

    async def test_handle_advances_the_read_position(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ops_log, "STREAM_CURSOR_FILE", tmp_path / "s.json")
        monkeypatch.setattr(ops_log, "append_op", lambda row: None)
        c = ops_log.OpsLogConsumer("did:plc:phi")
        await c._handle(
            json.dumps(
                {
                    "did": "did:plc:phi",
                    "kind": "commit",
                    "time_us": 5_000_000,
                    "commit": {
                        "operation": "create",
                        "collection": "app.bsky.feed.like",
                        "rkey": "r",
                    },
                }
            )
        )
        assert ops_log._stream_cursor() == 5_000_000


def test_endpoint_rotates_on_each_attempt(monkeypatch):
    from bot.config import settings

    monkeypatch.setattr(
        settings, "jetstream_urls", ("wss://a/subscribe", "wss://b/subscribe")
    )
    c = ops_log.OpsLogConsumer("did:plc:phi")
    assert c._url().startswith("wss://a/subscribe?")
    c._attempt += 1
    assert c._url().startswith("wss://b/subscribe?")
    c._attempt += 1
    assert c._url().startswith("wss://a/subscribe?")
