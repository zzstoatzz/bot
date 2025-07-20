# Implementation Notes - Brain Dump

## Critical Details to Remember

### AT Protocol Authentication
- Use `client.send_post()` NOT manual record creation
- Authentication with app password, not main password
- Client auto-refreshes JWT tokens
- `get_current_time_iso()` for proper timestamp format

### Notification Handling (IMPORTANT!)
1. **Capture timestamp BEFORE fetching** - this is KEY
2. Process notifications
3. Mark as seen using INITIAL timestamp
4. This prevents missing notifications that arrive during processing

```python
check_time = self.client.client.get_current_time_iso()
# ... fetch and process ...
await self.client.mark_notifications_seen(check_time)
```

### Reply Structure
- Don't include @mention in reply text (Bluesky handles it)
- Build proper reply references:
```python
parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=post_uri, cid=post.cid)
reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
```

### Current Architecture
```
FastAPI (lifespan)
  └── NotificationPoller (async task)
      └── MessageHandler
          └── ResponseGenerator
              └── AnthropicAgent (when API key available)
              └── Placeholder responses (fallback)
```

### Key Files
- `src/bot/core/atproto_client.py` - Wrapped AT Protocol client (truly core)
- `src/bot/services/notification_poller.py` - Async polling with proper shutdown
- `src/bot/response_generator.py` - Simple response generation with AI fallback
- `src/bot/agents/anthropic_agent.py` - Anthropic Claude integration

### Testing
- `scripts/test_post.py` - Creates post and reply
- `scripts/test_mention.py` - Mentions bot from another account
- Need TEST_BLUESKY_HANDLE and TEST_BLUESKY_PASSWORD in .env

### Dependencies
- `atproto` - Python SDK for Bluesky
- `pydantic-settings` - Config management
- `pydantic-ai` - LLM agent framework
- `anthropic` - Claude API client
- `ty` - Astral's new type checker (replaces pyright)

### Graceful Shutdown
- Don't await the task twice in lifespan
- Handle CancelledError in the poll loop
- Check if task is done before cancelling

### Memory Plans (Not Implemented)
1. **Core Memory** - Bot personality (namespace: bot_core)
2. **User Memory** - Per-user facts (namespace: user_{did})
3. **Conversation Memory** - Recent context (namespace: conversations)

### TurboPuffer Notes
- 10x cheaper than traditional vector DBs
- Use namespaces for isolation
- Good for millions of users
- Has Python SDK

### Thread History (Implemented)
- SQLite database for thread message storage
- Tracks threads by root URI
- Stores all messages with author info
- Full thread context passed to AI agent
- Inspired by Marvin's simple approach

### Next Session TODOs
1. Add `turbopuffer` dependency for vector memory
2. Create `MemoryManager` service for user facts
3. Improve system prompt DX (like Marvin's @agent.system_prompt)
4. Add memory retrieval to message context
5. Consider admin-only mode initially (like Penelope)

### Gotchas Discovered
- `update_seen` takes params dict, not data dict
- Notifications have `indexed_at` not `created_at`
- Hot reload causes CancelledError (now handled)
- atproto client has `send_post()` helper method

### Reference Insights
- **Void**: File-based queue, processed_notifications.json tracking
- **Penelope**: Admin-only initially, can self-modify profile
- **Marvin**: User-namespaced vectors, progress tracking

### Bot Behavior
- Only responds to mentions (not likes, follows)
- Polls every 10 seconds (configurable)
- Marks notifications read to avoid duplicates
- Has local cache as safety net