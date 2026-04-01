# Phi Evaluations

Behavioral tests for phi using LLM-as-judge evaluation.

## Structure

Inspired by [prefect-mcp-server evals](https://github.com/PrefectHQ/prefect-mcp-server/tree/main/evals).

```
evals/
├── conftest.py                # Test fixtures, evaluator, and ToolCallSpy
├── test_basic_responses.py    # Basic response behavior
├── test_feed_creation.py      # Graze feed tool usage
├── test_feed_consumption.py   # Feed reading, following, and owner-gating
└── test_memory_integration.py # Episodic memory tests
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

# Run only feed creation tests
uv run pytest evals/test_feed_creation.py -v
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

### Feed Creation (graze)
- ✅ Creates feed from natural language description
- ✅ Manifest uses valid graze DSL operators
- ✅ Handles complex/ambiguous descriptions (e.g. "rust programming, not the game")
- ✅ Lists feeds when asked (calls `list_feeds`, not `create_feed`)
- ✅ No tool calls for informational questions about feeds

### Feed Consumption & Following
- ✅ Reads timeline when asked
- ✅ Reads specific custom feed by name (via list_feeds → read_feed)
- ✅ Owner can ask phi to follow users
- ✅ Non-owner follow requests are denied
- ✅ Non-owner feed creation requests are denied
- ✅ Empty timeline suggests following accounts

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
- feed creation tests require only `ANTHROPIC_API_KEY` (tools are mocked via `ToolCallSpy`)
- feed consumption tests require only `ANTHROPIC_API_KEY` (tools are mocked via `ToolCallSpy`)
- no mocking required for basic/memory tests - they work with real mcp server and episodic memory

this ensures phi's behavior can be validated in various environments.
