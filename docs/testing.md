# testing

phi uses behavioral testing with llm-as-judge evaluation.

## philosophy

**test outcomes, not implementation**

we care that phi:
- replies appropriately to mentions
- uses thread context correctly
- maintains consistent personality
- makes reasonable action decisions

we don't care:
- which exact HTTP calls were made
- internal state of the agent
- specific tool invocation order

## test structure

```python
async def test_thread_awareness():
    """phi should reference thread context in replies"""

    # arrange: create thread context
    thread_context = """
    @alice: I love birds
    @phi: me too! what's your favorite?
    """

    # act: process new mention
    response = await agent.process_mention(
        mention_text="especially crows",
        author_handle="alice.bsky.social",
        thread_context=thread_context
    )

    # assert: behavioral check
    assert response.action == "reply"
    assert any(word in response.text.lower()
              for word in ["bird", "crow", "favorite"])
```

## llm-as-judge

for subjective qualities (tone, relevance, personality):

```python
async def test_personality_consistency():
    """phi should maintain grounded, honest tone"""

    response = await agent.process_mention(...)

    # use claude opus to evaluate
    evaluation = await judge_response(
        response=response.text,
        criteria=[
            "grounded (not overly philosophical)",
            "honest about capabilities",
            "concise for bluesky's 300 char limit"
        ]
    )

    assert evaluation.passes_criteria
```

## what we test

### unit tests
- memory operations (store/retrieve)
- thread context building
- response parsing

### integration tests
- full mention handling flow
- thread discovery
- decision making

### behavioral tests (evals)
- personality consistency
- thread awareness
- appropriate action selection
- memory utilization

## mocking strategy

**mock external services, not internal logic**

- mock ATProto client (don't actually post to bluesky)
- mock TurboPuffer (in-memory dict instead of network calls)
- mock MCP server (fake tool implementations)

**keep agent logic real** - we want to test actual decision making.

## running tests

```bash
just test        # unit tests
just evals       # behavioral tests with llm-as-judge
just check       # full suite (lint + typecheck + test)
```

## test isolation

tests never touch production:
- no real bluesky posts
- separate turbopuffer namespace for tests
- deterministic mock responses where needed

see `sandbox/TESTING_STRATEGY.md` for detailed approach.
