# Phi Evaluations

Behavioral tests for phi using LLM-as-judge evaluation.

## Structure

Inspired by [prefect-mcp-server evals](https://github.com/PrefectHQ/prefect-mcp-server/tree/main/evals).

```
evals/
├── conftest.py              # Test fixtures and evaluator
├── test_basic_responses.py  # Basic response behavior
└── test_memory_integration.py  # Episodic memory tests
```

## Running Evals

```bash
# Run all evals (tests will skip if API keys are missing)
uv run pytest evals/ -v

# Run specific eval
uv run pytest evals/test_basic_responses.py::test_phi_responds_to_philosophical_question -v

# Run only basic response tests
uv run pytest evals/test_basic_responses.py -v

# Run only memory tests
uv run pytest evals/test_memory_integration.py -v
```

## Environment Variables

Tests will **skip gracefully** if required API keys are missing.

**Required for all evals:**
- `ANTHROPIC_API_KEY` - For phi agent and LLM evaluator

**Required for memory evals only:**
- `TURBOPUFFER_API_KEY` - For episodic memory storage
- `OPENAI_API_KEY` - For embeddings

**Required for ATProto MCP tools (used by agent):**
- `BLUESKY_HANDLE` - Bot's Bluesky handle
- `BLUESKY_PASSWORD` - Bot's app password

## Evaluation Approach

Each eval:
1. **Sets up a scenario** - Simulates a mention/interaction
2. **Runs phi agent** - Gets structured response
3. **Makes assertions** - Checks basic structure
4. **LLM evaluation** - Uses Claude Opus to judge quality

**Important:** The `phi_agent` fixture is session-scoped, meaning all tests share one agent instance. Combined with session persistence (tokens saved to `.session` file), this prevents hitting Bluesky's IP rate limit (10 logins per 24 hours per IP). The session is reused across test runs unless tokens expire (~2 months).

Example:
```python
@pytest.mark.asyncio
async def test_phi_responds_to_philosophical_question(evaluate_response):
    agent = PhiAgent()

    response = await agent.process_mention(
        mention_text="what do you think consciousness is?",
        author_handle="test.user",
        thread_context="...",
        thread_uri="...",
    )

    # Structural check
    assert response.action == "reply"

    # Quality evaluation
    await evaluate_response(
        evaluation_prompt="Does the response engage thoughtfully?",
        agent_response=response.text,
    )
```

## What We Test

### Basic Responses
- ✅ Philosophical engagement
- ✅ Spam detection
- ✅ Thread context awareness
- ✅ Character limit compliance
- ✅ Casual interactions

### Memory Integration
- ✅ Episodic memory retrieval
- ✅ Conversation storage
- ✅ User-specific context

## Adding New Evals

1. Create test file: `evals/test_<category>.py`
2. Use fixtures from `conftest.py`
3. Write scenario-based tests
4. Use `evaluate_response` for quality checks

Example:
```python
@pytest.mark.asyncio
async def test_new_behavior(temp_memory, personality, evaluate_response):
    agent = PhiAgent()

    response = await agent.process_mention(...)

    await evaluate_response(
        evaluation_prompt="Your evaluation criteria here",
        agent_response=response.text,
    )
```

## ci integration

these evals are designed to run in ci with graceful degradation:
- tests skip automatically when required api keys are missing
- basic response tests require only `ANTHROPIC_API_KEY` and bluesky credentials
- memory tests require `TURBOPUFFER_API_KEY` and `OPENAI_API_KEY`
- no mocking required - tests work with real mcp server and episodic memory

this ensures phi's behavior can be validated in various environments.
