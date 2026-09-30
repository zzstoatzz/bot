"""scripts/voice_tics.py stays comparable across voice windows."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "voice_tics", Path(__file__).parent.parent / "scripts" / "voice_tics.py"
)
assert _spec and _spec.loader
voice_tics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(voice_tics)

DID = voice_tics.DID


def _record(rkey: str, at: str, text: str, parent: str | None = None) -> dict:
    value: dict = {"createdAt": at, "text": text}
    if parent:
        value["reply"] = {"parent": {"uri": parent}, "root": {"uri": parent}}
    return {"uri": f"at://{DID}/app.bsky.feed.post/{rkey}", "value": value}


def test_self_replies_join_and_alerts_drop():
    head = _record("a", "2026-09-01T00:00:00Z", "first part")
    cont = _record("b", "2026-09-01T00:00:01Z", "second part", parent=head["uri"])
    other = _record(
        "c", "2026-09-01T00:00:02Z", "reply to someone", parent="at://did:plc:x/p/1"
    )
    alert = _record("d", "2026-09-01T00:00:03Z", "@zzstoatzz.io flow CRASHED")

    posts = voice_tics.posts([cont, alert, other, head])

    assert [p["text"] for p in posts] == ["first part second part", "reply to someone"]


def test_measure_counts_posts_with_each_habit():
    window = [
        {"at": "t", "text": "The plagiarism was airtight. The linux box was not."},
        {
            "at": "t",
            "text": "that boundary is the design, not an afterthought — really.",
        },
    ]
    m = voice_tics.measure(window)

    assert m["em dash"] == 50
    assert m["X, not Y"] == 50
    assert m["lowercase start"] == 50
    assert m["short moral closer"] == 100
