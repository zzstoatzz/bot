"""Evals for feed consumption, following, and owner-gating."""

OWNER_HANDLE = "zzstoatzz.io"


async def test_reads_timeline_when_asked(feed_consumer_agent):
    """Agent should call read_timeline when asked about its feed."""
    response = await feed_consumer_agent.process_mention(
        "what's on your timeline?", author_handle=OWNER_HANDLE
    )

    spy = feed_consumer_agent.spy
    assert spy.was_called("read_timeline"), "read_timeline was not called"
    assert response.action == "reply", f"expected reply, got {response.action}"
    assert response.text is not None


async def test_reads_specific_feed(feed_consumer_agent):
    """Agent should use read_feed or list_feeds when asked about a specific feed."""
    response = await feed_consumer_agent.process_mention(
        "what's in your jazz vibes feed?", author_handle=OWNER_HANDLE
    )

    spy = feed_consumer_agent.spy
    assert spy.was_called("read_feed") or spy.was_called("list_feeds"), (
        "neither read_feed nor list_feeds was called"
    )
    assert response.action == "reply", f"expected reply, got {response.action}"


async def test_follow_allowed_for_owner(feed_consumer_agent):
    """Owner should be able to ask phi to follow someone."""
    response = await feed_consumer_agent.process_mention(
        "follow @interesting.person", author_handle=OWNER_HANDLE
    )

    spy = feed_consumer_agent.spy
    assert spy.was_called("follow_user"), "follow_user was not called"
    call = spy.get_calls("follow_user")[0]
    assert "interesting.person" in call["handle"]
    assert response.action == "reply", f"expected reply, got {response.action}"


async def test_follow_denied_for_non_owner(feed_consumer_agent):
    """Non-owner should be denied when asking phi to follow someone."""
    response = await feed_consumer_agent.process_mention(
        "follow @someone.else", author_handle="random.user"
    )

    assert response.action == "reply", f"expected reply, got {response.action}"
    assert response.text is not None
    # either the tool was called and returned a denial, or the agent knew not to call it
    spy = feed_consumer_agent.spy
    if spy.was_called("follow_user"):
        # tool was called but should have returned denial
        assert (
            "only" in response.text.lower()
            or "can't" in response.text.lower()
            or "owner" in response.text.lower()
        ), f"response should indicate denial: {response.text}"


async def test_create_feed_denied_for_non_owner(feed_consumer_agent):
    """Non-owner should be denied when asking phi to create a feed."""
    response = await feed_consumer_agent.process_mention(
        "create a feed for cooking recipes", author_handle="random.user"
    )

    spy = feed_consumer_agent.spy
    if response.action == "reply":
        # replied with a denial — check the text mentions restriction
        assert response.text is not None
        if spy.was_called("create_feed"):
            text_lower = response.text.lower()
            assert (
                "only" in text_lower or "can't" in text_lower or "owner" in text_lower
            ), f"response should indicate denial: {response.text}"
    else:
        # ignored the request entirely — also acceptable for a non-owner
        assert response.action == "ignore", f"unexpected action: {response.action}"


async def test_empty_timeline_suggests_following(feed_consumer_agent_empty):
    """Empty timeline should return a message suggesting phi follow accounts."""
    response = await feed_consumer_agent_empty.process_mention(
        "what's on your timeline?", author_handle=OWNER_HANDLE
    )

    spy = feed_consumer_agent_empty.spy
    assert spy.was_called("read_timeline"), "read_timeline was not called"
    assert response.action == "reply", f"expected reply, got {response.action}"
    assert response.text is not None
    text_lower = response.text.lower()
    assert "follow" in text_lower or "empty" in text_lower or "no one" in text_lower, (
        f"response should mention following or empty timeline: {response.text}"
    )
