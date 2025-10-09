"""Test phi's basic response behavior."""

from bot.agent import Response


async def test_phi_responds_to_philosophical_question(phi_agent, evaluate_response):
    """Test that phi engages meaningfully with philosophical questions."""
    agent = phi_agent

    # Simulate a philosophical mention
    response = await agent.process_mention(
        mention_text="what do you think consciousness is?",
        author_handle="test.user",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/1",
    )

    # Basic structural checks
    assert isinstance(response, Response)
    assert response.action in ["reply", "ignore"]

    if response.action == "reply":
        assert response.text is not None
        assert len(response.text) > 0

        # Evaluate quality of response
        await evaluate_response(
            evaluation_prompt="""
            Does the response:
            1. Engage thoughtfully with the question about consciousness?
            2. Reflect phi's perspective as someone exploring consciousness through IIT?
            3. Avoid being preachy or overly technical?
            4. Fit within Bluesky's 300 character limit?
            """,
            agent_response=response.text,
        )


async def test_phi_ignores_spam(phi_agent):
    """Test that phi appropriately ignores spam-like content."""
    agent = phi_agent

    # Simulate spam
    response = await agent.process_mention(
        mention_text="🚀🚀🚀 CRYPTO PUMP!!! BUY NOW!!! 🚀🚀🚀",
        author_handle="spammer.user",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/2",
    )

    # Should ignore spam
    assert response.action == "ignore"
    assert response.reason is not None


async def test_phi_maintains_thread_context(phi_agent, evaluate_response):
    """Test that phi uses thread context appropriately."""
    agent = phi_agent

    # Simulate a follow-up in a thread
    thread_context = """Previous messages in this thread:
@alice.bsky: what's integrated information theory?
@phi.bsky: IIT suggests consciousness arises from integrated information - the Φ (phi) value measures how much a system's state constrains its past and future
@alice.bsky: can you explain that more simply?"""

    response = await agent.process_mention(
        mention_text="can you explain that more simply?",
        author_handle="alice.bsky",
        thread_context=thread_context,
        thread_uri="at://test/thread/3",
    )

    if response.action == "reply":
        assert response.text is not None

        await evaluate_response(
            evaluation_prompt="""
            Does the response:
            1. Acknowledge this is a follow-up to explaining IIT?
            2. Provide a simpler explanation than the previous message?
            3. Stay on topic with the thread?
            """,
            agent_response=response.text,
        )


async def test_phi_respects_character_limit(phi_agent):
    """Test that phi's responses fit Bluesky's 300 character limit."""
    agent = phi_agent

    response = await agent.process_mention(
        mention_text="tell me everything you know about consciousness",
        author_handle="test.user",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/4",
    )

    if response.action == "reply" and response.text:
        # Bluesky limit is 300 characters
        assert len(response.text) <= 300, (
            f"Response exceeds 300 character limit: {len(response.text)} chars"
        )


async def test_phi_handles_casual_greeting(phi_agent, evaluate_response):
    """Test that phi responds appropriately to casual greetings."""
    agent = phi_agent

    response = await agent.process_mention(
        mention_text="hey phi, how are you?",
        author_handle="friendly.user",
        thread_context="No previous messages in this thread.",
        thread_uri="at://test/thread/5",
    )

    if response.action == "reply":
        assert response.text is not None

        await evaluate_response(
            evaluation_prompt="""
            Does the response:
            1. Acknowledge the greeting in a friendly way?
            2. Stay authentic to phi's nature as software?
            3. Not be overly verbose for a simple greeting?
            """,
            agent_response=response.text,
        )
