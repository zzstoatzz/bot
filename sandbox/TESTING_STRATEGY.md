# testing strategy for phi

## goal
test behavior/outcomes cleanly without polluting production environments (bluesky, turbopuffer, etc.)

## principles
1. **test outcomes, not implementation** - we care that phi replies appropriately, not that it made specific HTTP calls
2. **isolated test environments** - tests should never touch production bluesky, turbopuffer, or post real content
3. **behavioral assertions** - test what phi does (reply, ignore, like) and what it says, not how it does it
4. **fixture-based mocking** - use pytest fixtures to provide test doubles that are reusable across tests

## what to test

### behavior tests (high-level)
- **mention handling**: does phi reply when mentioned? does it use thread context?
- **memory integration**: does phi retrieve and use relevant memories?
- **decision making**: does phi choose the right action (reply/ignore/like/repost)?
- **content quality**: does phi's response match its personality? (llm-as-judge)

### unit tests (low-level)
- **memory operations**: storing/retrieving memories works correctly
- **thread context**: building conversation context from thread history
- **response parsing**: structured output (Response model) is valid

## what NOT to test
- exact HTTP calls to bluesky API
- exact vector embeddings used
- implementation details of atproto client
- exact format of turbopuffer queries

## mocking strategy

### level 1: mock external services (clean boundary)
```python
@pytest.fixture
def mock_atproto_client():
    """Mock ATProto client that doesn't actually post to bluesky"""
    class MockClient:
        def __init__(self):
            self.posts = []  # track what would have been posted
            self.me = MockMe()

        def send_post(self, text, reply_to=None):
            self.posts.append({"text": text, "reply_to": reply_to})
            return MockPostRef()

    return MockClient()

@pytest.fixture
def mock_memory():
    """Mock memory that uses in-memory dict instead of turbopuffer"""
    class MockMemory:
        def __init__(self):
            self.memories = {}

        async def store_user_memory(self, handle, content, memory_type):
            if handle not in self.memories:
                self.memories[handle] = []
            self.memories[handle].append(content)

        async def build_conversation_context(self, handle, include_core=False, query=None):
            # return relevant memories without hitting turbopuffer
            return "\n".join(self.memories.get(handle, []))

    return MockMemory()
```

### level 2: mock agent responses (for deterministic tests)
```python
@pytest.fixture
def mock_agent_response():
    """Return pre-determined responses instead of hitting Claude API"""
    def _mock(mention_text: str) -> Response:
        # simple rule-based responses for testing
        if "hello" in mention_text.lower():
            return Response(action="reply", text="hi there!", reason=None)
        elif "spam" in mention_text.lower():
            return Response(action="ignore", text=None, reason="spam")
        else:
            return Response(action="reply", text="interesting point", reason=None)

    return _mock
```

### level 3: integration fixtures (compose mocks)
```python
@pytest.fixture
def test_phi_agent(mock_atproto_client, mock_memory):
    """Create a phi agent with mocked dependencies for integration tests"""
    agent = PhiAgent()
    agent.client = mock_atproto_client
    agent.memory = mock_memory
    # agent still uses real Claude for responses (can be slow but tests real behavior)
    return agent

@pytest.fixture
def fully_mocked_phi_agent(mock_atproto_client, mock_memory, mock_agent_response):
    """Create a fully mocked phi agent for fast unit tests"""
    agent = PhiAgent()
    agent.client = mock_atproto_client
    agent.memory = mock_memory
    agent._generate_response = mock_agent_response  # deterministic responses
    return agent
```

## test environments

### approach 1: environment variable switching
```python
# conftest.py
@pytest.fixture(scope="session", autouse=True)
def test_environment():
    """Force test environment settings"""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["TURBOPUFFER_NAMESPACE"] = "phi-test"  # separate test namespace
    # could use a different bluesky account too
    yield
    # cleanup test data after all tests
```

### approach 2: dependency injection
```python
# bot/agent.py
class PhiAgent:
    def __init__(self, client=None, memory=None, llm=None):
        self.client = client or create_production_client()
        self.memory = memory or create_production_memory()
        self.llm = llm or create_production_llm()
```

This makes testing clean:
```python
def test_mention_handling(mock_client, mock_memory):
    agent = PhiAgent(client=mock_client, memory=mock_memory)
    # test with mocked dependencies
```

## example test cases

### integration test (uses real LLM, mocked infrastructure)
```python
async def test_phi_uses_thread_context_in_response(test_phi_agent):
    """Phi should reference previous messages in thread when replying"""

    # setup: create a thread with context
    thread_context = """
    Previous messages:
    @alice: I love birds
    @phi: me too! what's your favorite?
    """

    # act: phi processes a new mention
    response = await test_phi_agent.process_mention(
        mention_text="especially crows",
        author_handle="alice.test",
        thread_context=thread_context,
        thread_uri="at://test/thread/1"
    )

    # assert: phi replies and references the conversation
    assert response.action == "reply"
    assert response.text is not None
    # behavioral assertion - should show awareness of context
    assert any(word in response.text.lower() for word in ["bird", "crow", "favorite"])
```

### unit test (fully mocked, fast)
```python
async def test_phi_ignores_spam(fully_mocked_phi_agent):
    """Phi should ignore obvious spam"""

    response = await fully_mocked_phi_agent.process_mention(
        mention_text="BUY CRYPTO NOW!!! spam spam spam",
        author_handle="spammer.test",
        thread_context="No previous messages",
        thread_uri="at://test/thread/2"
    )

    assert response.action == "ignore"
    assert response.reason is not None
```

### memory test
```python
async def test_memory_stores_user_interactions(mock_memory):
    """Memories should persist user interactions"""

    await mock_memory.store_user_memory(
        "alice.test",
        "Alice mentioned she loves birds",
        MemoryType.USER_FACT
    )

    context = await mock_memory.build_conversation_context("alice.test")

    assert "birds" in context.lower()
```

## fixture organization

```
tests/
├── conftest.py           # shared fixtures
│   ├── settings          # test settings
│   ├── mock_client       # mock atproto client
│   ├── mock_memory       # mock turbopuffer
│   └── test_phi_agent    # composed test agent
├── unit/
│   ├── test_memory.py    # memory operations
│   └── test_response.py  # response generation
└── integration/
    ├── test_mentions.py  # full mention handling flow
    └── test_threads.py   # thread context handling
```

## key challenges

1. **mocking MCP tools** - phi uses atproto MCP server for posting
   - solution: mock the entire MCP transport or provide fake tool implementations

2. **testing non-deterministic LLM responses** - claude's responses vary
   - solution: use llm-as-judge for behavioral assertions instead of exact text matching
   - alternative: mock agent responses for unit tests, use real LLM for integration tests

3. **async testing** - everything is async
   - solution: use pytest-asyncio (already doing this)

4. **test data cleanup** - don't leave garbage in test environments
   - solution: use separate test namespaces, clean up in fixture teardown

## next steps

1. create mock implementations of key dependencies (client, memory)
2. add dependency injection to PhiAgent for easier testing
3. write a few example tests to validate the approach
4. decide on integration vs unit test balance
