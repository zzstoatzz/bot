# MCP Refactor Progress

## Branch: `mcp-refactor`

## Completed ✅

### Phase 1: Foundation
1. **Cloned and studied reference projects**
   - `sandbox/prefect-mcp-server` - Learned PydanticAI + MCP patterns
   - Understood how MCP servers work as toolsets for PydanticAI agents

2. **Created simplified memory system** (`src/bot/memory.py`)
   - Single SQLite database (threads.db)
   - Plain text storage - no embeddings, no vector search
   - Two tables:
     - `threads` - Full conversation history per thread (JSON)
     - `user_memories` - Simple facts about users
   - Completely interpretable - you can open the db and read everything

3. **Integrated ATProto MCP server**
   - Copied from `.eggs/fastmcp/examples/atproto_mcp` → `src/bot/atproto_mcp`
   - Updated settings to use existing env vars (BLUESKY_HANDLE, etc.)
   - Server provides tools: post(), like(), repost(), follow(), search(), create_thread()

4. **Created MCP-enabled agent** (`src/bot/agent.py`)
   - PydanticAI Agent with ATProto MCP tools as a toolset
   - Loads personality from `personalities/phi.md`
   - Integrates with memory system
   - Returns structured Response (action, text, reason)

5. **Updated dependencies**
   - ✅ Added: `fastmcp>=0.8.0`, `websockets>=15.0.1`
   - ❌ Removed: `turbopuffer`, `openai` (no longer needed for memory)

## What Changed

### Before (Complex)
- **Memory**: TurboPuffer + OpenAI embeddings + semantic search
- **Agent**: Custom response generator with manual action interpretation
- **AT Protocol**: Direct client calls scattered throughout codebase
- **Personality**: Dynamic loading from TurboPuffer
- **Self-modification**: Complex approval system with DM workflow

### After (Simple)
- **Memory**: SQLite with plain text (interpretable!)
- **Agent**: PydanticAI with MCP tools (agent decides actions)
- **AT Protocol**: MCP server provides all tools
- **Personality**: Static file loading
- **Self-modification**: Removed (cruft)

## How It Works Now

```python
# Create agent with memory
memory = Memory()
agent = PhiAgent(memory)

# Process a mention
response = await agent.process_mention(
    mention_text="hey phi!",
    author_handle="user.bsky.social",
    thread_uri="at://did/post/123"
)

# Agent returns: Response(action="reply", text="...", reason="...")
# If action is "reply", agent can call MCP tool: post(text="...", reply_to="...")
```

The agent has access to all ATProto MCP tools and can decide:
- Should I reply, like, or ignore this?
- If replying, what should I say?
- Should I use other tools (repost, follow, etc.)?

## Next Steps

### Phase 2: Integration (Not Started)
1. Update `src/bot/main.py` to use new agent
2. Simplify `src/bot/services/notification_poller.py`
3. Remove old response_generator.py
4. Test end-to-end

### Phase 3: Cleanup (Not Started)
1. Delete cruft:
   - `src/bot/ui/` (context visualization)
   - `src/bot/personality/editor.py` (approval system)
   - `src/bot/core/dm_approval.py`
   - `src/bot/memory/namespace_memory.py`
   - `src/bot/agents/anthropic_agent.py` (replaced by agent.py)
2. Update database.py to remove approval tables
3. Update tests
4. Update README.md and documentation

### Phase 4: Verification (Not Started)
1. Run the bot and test mentions
2. Verify thread memory works
3. Verify user memory works
4. Ensure online/offline status still works

## Testing

Test script created: `sandbox/test_new_agent.py`

```bash
uv run python sandbox/test_new_agent.py
```

## Key Files

### New
- `src/bot/memory.py` - Simple SQLite memory
- `src/bot/agent.py` - MCP-enabled PydanticAI agent
- `src/bot/atproto_mcp/` - ATProto MCP server (vendored)

### Modified
- `pyproject.toml` - Updated dependencies

### To Be Deleted
- `src/bot/memory/namespace_memory.py`
- `src/bot/agents/anthropic_agent.py`
- `src/bot/response_generator.py`
- `src/bot/ui/`
- `src/bot/personality/editor.py`
- `src/bot/core/dm_approval.py`

## Philosophy

**Before**: Over-engineered for capabilities we might want someday
**After**: Simple, working, interpretable system that does what we need today

The memory is now something you can:
1. Open with any SQLite browser
2. Read and understand immediately
3. Debug by just looking at the tables
4. Migrate or export trivially

No more:
- Vector embeddings you can't see
- Complex namespace hierarchies
- Approval workflows for every personality change
- Multiple overlapping memory systems
