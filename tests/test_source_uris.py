"""Tests for memory source-uri citations: model validation, role inference, render."""

from bot.memory.extraction import Observation
from bot.memory.namespace_memory import _citation_tail, _source_role

PHI_DID = "did:plc:65sucjiel52gefhcdcypynsr"
OWNER_DID = "did:plc:xbtmt2zjwlrfegqvch7fboei"
STRANGER_DID = "did:plc:abcdefghijklmnopqrstuvwx"


# --- Observation.source_uris validation ---


def test_observation_default_source_uris_empty():
    obs = Observation(content="x cares about y", tags=["interest"])
    assert obs.source_uris == []


def test_observation_accepts_valid_at_uri():
    obs = Observation(
        content="x cares about y",
        tags=["interest"],
        source_uris=[f"at://{STRANGER_DID}/app.bsky.feed.post/3mjuabmoh2o22"],
    )
    assert len(obs.source_uris) == 1


def test_observation_accepts_multiple_uris():
    obs = Observation(
        content="x cares about y",
        tags=[],
        source_uris=[
            f"at://{STRANGER_DID}/app.bsky.feed.post/3mjuabmoh2o22",
            f"at://{STRANGER_DID}/app.bsky.feed.post/3mjuabmoh2o23",
        ],
    )
    assert len(obs.source_uris) == 2


# --- _source_role match/case classification ---


def test_role_phi_post_with_did_context():
    uri = f"at://{PHI_DID}/app.bsky.feed.post/3mjuabmoh2o22"
    assert _source_role(uri, phi_did=PHI_DID, owner_did=OWNER_DID) == "phi-post"


def test_role_phi_post_without_did_context_falls_to_their_post():
    uri = f"at://{PHI_DID}/app.bsky.feed.post/3mjuabmoh2o22"
    # Without phi_did context, we can't distinguish phi from other authors —
    # falls through to "their-post". This is the documented behavior.
    assert _source_role(uri) == "their-post"


def test_role_operator_liked_with_did_context():
    uri = f"at://{OWNER_DID}/app.bsky.feed.like/3mjuabmoh2o22"
    assert _source_role(uri, phi_did=PHI_DID, owner_did=OWNER_DID) == "operator-liked"


def test_role_their_post():
    uri = f"at://{STRANGER_DID}/app.bsky.feed.post/3mjuabmoh2o22"
    assert _source_role(uri, phi_did=PHI_DID, owner_did=OWNER_DID) == "their-post"


def test_role_essay():
    uri = f"at://{STRANGER_DID}/app.greengale.document/3mjuabmoh2o22"
    assert _source_role(uri) == "essay"


def test_role_card():
    uri = f"at://{STRANGER_DID}/network.cosmik.card/3mjuabmoh2o22"
    assert _source_role(uri) == "card"


def test_role_liked_by_other():
    uri = f"at://{STRANGER_DID}/app.bsky.feed.like/3mjuabmoh2o22"
    assert _source_role(uri, owner_did=OWNER_DID) == "liked-by-other"


def test_role_other_collection():
    uri = f"at://{STRANGER_DID}/com.example.unknown/abc"
    assert _source_role(uri) == "other"


def test_role_invalid_uri():
    assert _source_role("not a uri") == "unknown"


def test_role_empty_string():
    assert _source_role("") == "unknown"


# --- _citation_tail formatting ---


def test_tail_empty_returns_empty():
    assert _citation_tail([]) == ""


def test_tail_singular():
    assert _citation_tail(["at://x/y/z"]) == " (1 source)"


def test_tail_plural():
    uris = ["at://x/y/a", "at://x/y/b", "at://x/y/c"]
    assert _citation_tail(uris) == " (3 sources)"


def test_tail_with_age_only():
    from datetime import UTC, datetime, timedelta

    ts = (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
    out = _citation_tail([], ts)
    assert out.startswith(" (")
    assert "ago" in out
    assert "source" not in out


def test_tail_sources_and_age():
    from datetime import UTC, datetime, timedelta

    ts = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    out = _citation_tail(["at://x/y/a", "at://x/y/b"], ts)
    assert "2 sources" in out
    assert "ago" in out
    assert ", " in out  # comma separator between fields


def test_tail_invalid_age_falls_back_to_sources_only():
    out = _citation_tail(["at://x/y/a"], "not a timestamp")
    assert out == " (1 source)"
