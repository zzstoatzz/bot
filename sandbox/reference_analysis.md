# Reference Project Analysis for Bluesky Bot

This document analyzes three reference projects to extract patterns and insights for building our Bluesky virtual person bot.

## 1. Penelope (Go Implementation)

### Overview
Penelope is a Go-based Bluesky bot that demonstrates direct AT Protocol integration using the Indigo library.

### Key Features
- **Real-time firehose consumer**: Subscribes to `com.atproto.sync.subscribeRepos` for real-time events
- **WebSocket-based event streaming**: Maintains persistent connection to Bluesky relay
- **Chat integration**: Uses an LLM backend (appears to be Ollama) for generating responses
- **Reply-only interaction**: Only responds when mentioned by admin users
- **Clickhouse integration**: Stores data for analytics (though not critical for basic bot functionality)

### Core Patterns to Adopt
1. **Firehose subscription pattern**:
   - Connect via WebSocket to relay host
   - Handle repo commits with parallel scheduler (400 workers, 10 buffer)
   - Maintain cursor position for resumption after disconnects

2. **Post creation pattern**:
   - Use `atproto.RepoCreateRecord` for creating posts
   - Include proper reply threading with root and parent references
   - Set `createdAt` timestamp using `syntax.DatetimeNow()`

3. **Authentication flow**:
   - Create session with identifier/password
   - Use access JWT for authenticated requests
   - Store bot DID for self-identification

### Key Code Insights
```go
// Consumer pattern - maintains persistent connection
func (p *Penelope) startConsumer(ctx context.Context, cancel context.CancelFunc)

// Reply detection - checks if bot is mentioned in root or parent
if rootUri.Authority().String() != p.botDid && parentUri.Authority().String() != p.botDid {
    return nil
}

// Admin check - only responds to allowlisted users
if !slices.Contains(p.botAdmins, did) {
    return nil
}
```

## 2. Void (Python Implementation)

### Overview
Void is a sophisticated Python-based Bluesky bot powered by Google's Gemini 2.5 Pro and the Letta memory framework.

### Key Features
- **Persistent memory system**: Multi-layered memory architecture (core, recall, archival)
- **AT Protocol integration**: Uses `atproto` Python library
- **Tool-based architecture**: Modular tools for different actions (post, reply, search, etc.)
- **Queue-based processing**: Manages notifications through a file-based queue system
- **Self-directed behavior**: Has an open-ended directive "to exist"

### Core Patterns to Adopt
1. **Memory Architecture**:
   - Core memory: Limited context window with persona and active data
   - Recall memory: Searchable database of past conversations
   - Archival memory: Long-term storage with semantic search

2. **Tool System**:
   - Separate tools for post, reply, search, thread operations
   - Each tool is a self-contained module with clear interfaces
   - Tools handle authentication and API calls independently

3. **Notification Processing**:
   ```python
   # Queue-based approach
   QUEUE_DIR = Path(queue_config['base_dir'])
   QUEUE_ERROR_DIR = Path(queue_config['error_dir'])
   QUEUE_NO_REPLY_DIR = Path(queue_config['no_reply_dir'])
   ```

4. **Post Creation with Rich Text**:
   - Handles mentions and URLs with proper facet parsing
   - Supports thread creation with multiple posts
   - Language specification for internationalization

### Key Code Insights
```python
# Rich text facet handling
def create_new_bluesky_post(text: List[str], lang: str = "en-US") -> str:
    # Parse mentions with regex
    mention_regex = rb"(?:^|[$|\W])(@([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
    
    # Parse URLs
    url_regex = rb"(?:^|[$|\W])(https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"
```

## 3. Marvin Slackbot (FastAPI + pydantic-ai)

### Overview
Marvin is a Slack bot built with FastAPI and pydantic-ai, demonstrating modern async Python patterns for bot development.

### Key Features
- **FastAPI integration**: RESTful API for webhook handling
- **Async architecture**: Full async/await pattern throughout
- **Tool decoration system**: Wraps tools with monitoring and progress tracking
- **Database integration**: SQLite for conversation history
- **Research agent**: Specialized agent for deep topic research
- **Progress indicators**: Real-time updates during processing

### Core Patterns to Adopt
1. **FastAPI Structure**:
   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # Startup: Initialize database, load secrets
       async with Database.connect(DB_FILE) as db:
           app.state.db = db
           yield
       # Shutdown logic
   ```

2. **Agent Architecture**:
   - Uses pydantic-ai for structured agent creation
   - Tool functions with clear type hints and descriptions
   - Context passing through dependency injection

3. **Progress Tracking**:
   ```python
   progress = await create_progress_message(
       channel_id=channel_id, 
       thread_ts=thread_ts, 
       initial_text="🔄 Thinking..."
   )
   ```

4. **Tool Usage Pattern**:
   ```python
   with WatchToolCalls(settings=decorator_settings):
       result = await create_agent(model=settings.model_name).run(
           user_prompt=cleaned_message,
           message_history=conversation,
           deps=user_context,
       )
   ```

### Key Code Insights
- Comprehensive error handling with retries
- Token counting and message truncation for context limits
- Modular tool system with research delegation
- Clean separation of concerns (API, core logic, integrations)

## Recommended Architecture for Our Bot

Based on the analysis, here's the recommended approach:

### 1. **Language & Framework**
- **Python** with **FastAPI** (like Marvin) for easier LLM integration and async support
- **atproto** library (like Void) for Bluesky integration
- **pydantic-ai** or similar for agent orchestration

### 2. **Core Components**
```
src/
├── api.py          # FastAPI app with webhook endpoints
├── core.py         # Agent creation and memory management
├── bluesky.py      # AT Protocol integration
├── tools/          # Modular tool implementations
│   ├── post.py
│   ├── reply.py
│   ├── search.py
│   └── memory.py
├── queue.py        # Notification queue management
└── settings.py     # Configuration management
```

### 3. **Key Features to Implement**
1. **Firehose subscription** (from Penelope) for real-time events
2. **Memory system** (from Void) for personality persistence
3. **Tool architecture** (from all three) for modular capabilities
4. **Progress tracking** (from Marvin) for user feedback
5. **Queue-based processing** (from Void) for reliability

### 4. **Authentication & Session Management**
```python
# Hybrid approach combining patterns
class BlueskyClient:
    async def create_session(self):
        # From Penelope pattern
        session = await self.client.login(username, password)
        self.did = session.did
        self.access_token = session.access_jwt
        
    async def post(self, text: str, reply_to=None):
        # From Void pattern with rich text support
        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "facets": self._parse_facets(text)
        }
```

### 5. **Deployment Considerations**
- Use Docker (like Marvin) for consistent deployment
- Environment variables for secrets
- Persistent volume for memory/queue storage
- Health checks and monitoring endpoints

This architecture combines the real-time capabilities of Penelope, the sophisticated memory system of Void, and the clean async patterns of Marvin to create a robust Bluesky bot framework.