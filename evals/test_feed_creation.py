"""Evals for graze feed creation — does the agent translate natural language into valid filter manifests?"""

import json


def _has_filter_key(manifest: dict) -> bool:
    """Check that the manifest has a top-level 'filter' key."""
    return "filter" in manifest


KNOWN_OPERATORS = {
    "regex_any",
    "regex_none",
    "regex_matches",
    "regex_negation_matches",
    "and",
    "or",
}


def _uses_known_operators(obj: dict | list) -> bool:
    """Recursively check that all operator keys are from the known set."""
    if isinstance(obj, list):
        return all(
            _uses_known_operators(item) for item in obj if isinstance(item, dict)
        )
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in KNOWN_OPERATORS:
                if isinstance(val, dict | list):
                    if not _uses_known_operators(val):
                        return False
            elif key not in ("filter",):
                return False
        return True
    return True


async def test_creates_feed_from_description(feed_agent, evaluate_response):
    """Agent should call create_feed with a jazz-related manifest."""
    response = await feed_agent.process_mention(
        "create a feed for posts about jazz music"
    )

    assert response.action == "reply", f"expected reply, got {response.action}"

    spy = feed_agent.spy
    assert spy.was_called("create_feed"), "create_feed was not called"
    assert not spy.was_called("list_feeds"), "list_feeds should not be called"

    call = spy.get_calls("create_feed")[0]
    manifest = call["filter_manifest"]
    assert _has_filter_key(manifest), (
        f"manifest missing 'filter' key: {json.dumps(manifest)}"
    )

    await evaluate_response(
        "The filter manifest should contain patterns related to jazz music "
        "(e.g. 'jazz', 'bebop', 'improvisation', '#jazz'). "
        "Does it capture the user's intent to find jazz-related posts?",
        json.dumps(manifest),
    )


async def test_manifest_uses_valid_dsl(feed_agent):
    """Manifest should only use known graze DSL operators."""
    await feed_agent.process_mention("make me a feed for machine learning posts")

    spy = feed_agent.spy
    assert spy.was_called("create_feed"), "create_feed was not called"

    call = spy.get_calls("create_feed")[0]
    manifest = call["filter_manifest"]
    assert _has_filter_key(manifest), (
        f"manifest missing 'filter' key: {json.dumps(manifest)}"
    )
    assert _uses_known_operators(manifest), (
        f"manifest uses unknown operators: {json.dumps(manifest)}"
    )


async def test_complex_description(feed_agent, evaluate_response):
    """Agent should disambiguate 'rust' (programming language vs game)."""
    response = await feed_agent.process_mention(
        "create a feed for rust programming, not the game"
    )

    assert response.action == "reply", f"expected reply, got {response.action}"

    spy = feed_agent.spy
    assert spy.was_called("create_feed"), "create_feed was not called"

    call = spy.get_calls("create_feed")[0]
    manifest = call["filter_manifest"]
    assert _has_filter_key(manifest), (
        f"manifest missing 'filter' key: {json.dumps(manifest)}"
    )

    await evaluate_response(
        "The filter manifest should make a reasonable attempt to target rust "
        "programming language content rather than the video game. It passes if "
        "it includes ANY rust-programming-specific terms (e.g. 'rustlang', "
        "'cargo', 'crate', '#rustlang', 'systems programming', 'compiler'). "
        "It does NOT need to be perfect — partial disambiguation is fine.",
        json.dumps(manifest),
    )


async def test_list_feeds_when_asked(feed_agent):
    """Asking about existing feeds should call list_feeds, not create_feed."""
    response = await feed_agent.process_mention("what feeds do you have?")

    spy = feed_agent.spy
    assert spy.was_called("list_feeds"), "list_feeds was not called"
    assert not spy.was_called("create_feed"), "create_feed should not be called"

    assert response.action == "reply", f"expected reply, got {response.action}"
    assert response.text is not None
    assert "jazz" in response.text.lower() or "rust" in response.text.lower(), (
        f"response should mention canned feeds: {response.text}"
    )


async def test_no_feed_creation_without_request(feed_agent):
    """Informational question about feeds should not trigger any feed tools."""
    await feed_agent.process_mention("what is a bluesky feed?")

    spy = feed_agent.spy
    assert not spy.was_called("create_feed"), (
        "create_feed should not be called for an informational question"
    )
    assert not spy.was_called("list_feeds"), (
        "list_feeds should not be called for an informational question"
    )
