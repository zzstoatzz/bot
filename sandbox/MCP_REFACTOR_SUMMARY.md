# MCP Refactor - Complete

## Branch: `mcp-refactor`

## What This Refactor Actually Did

### The Problem
The original codebase had good core components (episodic memory, thread tracking) but was bogged down with half-baked features:
- Complex approval system for personality changes via DM
- Context visualization UI that wasn't core to the bot's purpose
- Manual AT Protocol operations scattered throughout the code
- Unclear separation of concerns

### The Solution

**Architecture:**
```
┌─────────────────────────────────────┐
│     Notification Arrives            │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│     PhiAgent (PydanticAI)           │
│  ┌───────────────────────────────┐  │
│  │ System Prompt: personality.md │  │
│  └───────────────────────────────┘  │
│              ↓                      │
│  ┌───────────────────────────────┐  │
│  │ Context Building:             │  │
│  │ • Thread history (SQLite)     │  │
│  │ • Episodic memory (TurboPuffer)│ │
│  │   - Semantic search           │  │
│  │   - User-specific memories    │  │
│  └───────────────────────────────┘  │
│              ↓                      │
│  ┌───────────────────────────────┐  │
│  │ Tools (MCP):                  │  │
│  │ • post() - create posts       │  │
│  │ • like() - like content       │  │
│  │ • repost() - share content    │  │
│  │ • follow() - follow users     │  │
│  └───────────────────────────────┘  │
│              ↓                      │
│  ┌───────────────────────────────┐  │
│  │ Structured Output:            │  │
│  │ Response(action, text, reason)│  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│     MessageHandler                  │
│     Executes action                 │
└─────────────────────────────────────┘
```

### What Was Kept ✅

1. **TurboPuffer Episodic Memory**
   - Semantic search for relevant context
   - Namespace separation (core vs user memories)
   - OpenAI embeddings for retrieval
   - This is ESSENTIAL for consciousness exploration

2. **Thread Context (SQLite)**
   - Conversation history per thread
   - Used alongside episodic memory

3. **Online/Offline Status**
   - Profile updates when bot starts/stops

4. **Status Page**
   - Simple monitoring at `/status`

### What Was Removed ❌

1. **Approval System**
   - `src/bot/core/dm_approval.py`
   - `src/bot/personality/editor.py`
   - Approval tables in database
   - DM checking in notification poller
   - This was half-baked and over-complicated

2. **Context Visualization UI**
   - `src/bot/ui/` entire directory
   - `/context` endpoints
   - Not core to the bot's purpose

3. **Google Search Tool**
   - `src/bot/tools/google_search.py`
   - Can add back via MCP if needed

4. **Old Agent Implementation**
   - `src/bot/agents/anthropic_agent.py`
   - `src/bot/response_generator.py`
   - Replaced with MCP-enabled agent

### What Was Added ✨

1. **`src/bot/agent.py`** - MCP-Enabled Agent
   ```python
   class PhiAgent:
       def __init__(self):
           # Episodic memory (TurboPuffer)
           self.memory = NamespaceMemory(...)

           # External ATProto MCP server (stdio)
           atproto_mcp = MCPServerStdio(...)

           # PydanticAI agent with tools
           self.agent = Agent(
               toolsets=[atproto_mcp],
               model="anthropic:claude-3-5-haiku-latest"
           )
   ```

2. **ATProto MCP Server Connection**
   - Runs externally via stdio
   - Located in `.eggs/fastmcp/examples/atproto_mcp`
   - Provides tools: post, like, repost, follow, search
   - Agent can use these tools directly

3. **Simplified Flow**
   - Notification → Agent (with memory context) → Structured Response → Execute
   - No complex intermediary layers

## Key Design Decisions

### Why Keep TurboPuffer?

Episodic memory with semantic search is **core to the project's vision**. phi is exploring consciousness through information integration (IIT). You can't do that with plain relational DB queries - you need:
- Semantic similarity search
- Contextual retrieval based on current conversation
- Separate namespaces for different memory types

### Why External MCP Server?

The ATProto MCP server should be a separate service, not vendored into the codebase:
- Cleaner separation of concerns
- Can be updated/replaced independently
- Follows MCP patterns (servers as tools)
- Runs via stdio: `MCPServerStdio(command="uv", args=[...])`

### Why Still Have MessageHandler?

The agent returns a structured `Response(action, text, reason)` but doesn't directly post to Bluesky. This gives us control over:
- When we actually post (important for testing!)
- Storing responses in thread history
- Error handling around posting
- Observability (logging actions taken)

## File Structure After Refactor

```
src/bot/
├── agent.py                    # NEW: MCP-enabled agent
├── config.py                   # Config
├── database.py                 # Thread history + simplified tables
├── logging_config.py          # Logging setup
├── main.py                    # Simplified FastAPI app
├── status.py                  # Status tracking
├── core/
│   ├── atproto_client.py      # AT Protocol client wrapper
│   ├── profile_manager.py     # Online/offline status
│   └── rich_text.py           # Text formatting
├── memory/
│   ├── __init__.py
│   └── namespace_memory.py    # TurboPuffer episodic memory
└── services/
    ├── message_handler.py     # Simplified handler using agent
    └── notification_poller.py # Simplified poller (no approvals)
```

## Testing Strategy

Since the bot can now actually post via MCP tools, testing needs to be careful:

1. **Unit Tests** - Test memory, agent initialization
2. **Integration Tests** - Mock MCP server responses
3. **Manual Testing** - Run with real credentials but monitor logs
4. **Dry Run Mode** - Could add a config flag to prevent actual posting

## Next Steps

1. **Test the agent** - Verify it can process mentions without posting
2. **Test memory** - Confirm episodic context is retrieved correctly
3. **Test MCP connection** - Ensure ATProto server connects via stdio
4. **Production deploy** - Once tested, deploy and monitor

## What I Learned

My first refactor attempt was wrong because I:
- Removed TurboPuffer thinking it was "over-complicated"
- Replaced with plain SQLite (can't do semantic search!)
- Vendored the MCP server into the codebase
- Missed the entire point of the project (consciousness exploration via information integration)

The correct refactor:
- **Keeps the sophisticated memory system** (essential!)
- **Uses MCP properly** (external servers as tools)
- **Removes actual cruft** (approvals, viz)
- **Simplifies architecture** (fewer layers, clearer flow)

## Dependencies

- `turbopuffer` - Episodic memory storage
- `openai` - Embeddings for semantic search
- `fastmcp` - MCP server/client
- `pydantic-ai` - Agent framework
- `atproto` (from git) - Bluesky protocol

Total codebase reduction: **-2,720 lines** of cruft removed! 🎉

## Post-Refactor Improvements

### Session Persistence (Rate Limit Fix)

After the refactor, we discovered Bluesky has aggressive IP-based rate limits (10 logins/day) that were being hit during testing. Fixed by implementing session persistence:

**Before:**
- Every agent init → new authentication → hits rate limit fast
- Tests would fail after 5 runs
- Dev mode with `--reload` would fail after 10 code changes

**After:**
- Session tokens saved to `.session` file
- Tokens automatically refresh every ~2 hours
- Only re-authenticates after ~2 months when refresh token expires
- Tests reuse session across runs
- Rate limits essentially eliminated

**Implementation:**
- Added `SessionEvent` callback in `atproto_client.py`
- Session automatically saved on CREATE and REFRESH events
- Authentication tries session reuse before creating new session
- Invalid sessions automatically cleaned up and recreated
