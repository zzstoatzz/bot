# Architecture Synthesis: Building a Bluesky Bot

## Overview
Combining insights from three reference implementations to create a sophisticated Bluesky virtual person:
- **Marvin**: Multi-agent architecture with vector memory
- **Void**: Sophisticated memory layers with strong personality
- **Penelope**: Clean AT Protocol integration with safety features

## Proposed Architecture

### 1. Core Components

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                   │
├─────────────────────────────────────────────────────────┤
│  Lifespan Manager                                       │
│  ├── AT Protocol Client (auth, posting)                │
│  ├── Notification Poller (async task)                  │
│  └── Memory Manager (TurboPuffer)                      │
├─────────────────────────────────────────────────────────┤
│  Message Handler                                        │
│  ├── Context Builder (thread + memory)                 │
│  ├── LLM Agent (pydantic-ai)                          │
│  └── Response Publisher                                │
└─────────────────────────────────────────────────────────┘
```

### 2. Memory Architecture (Inspired by Void + TurboPuffer)

#### Three-Tier Memory System
1. **Core Memory** (bot namespace)
   - Personality definition
   - Behavioral guidelines
   - Global knowledge

2. **User Memory** (user_{did} namespaces)
   - Facts about users
   - Conversation history
   - Relationship context

3. **Archival Memory** (archive namespace)
   - Semantic search across all interactions
   - Pattern recognition
   - Long-term learning

#### Implementation with TurboPuffer
```python
class MemoryManager:
    def __init__(self, turbopuffer_client):
        self.client = turbopuffer_client
        self.core_namespace = "bot_core"
        
    async def load_user_context(self, user_did: str):
        namespace = f"user_{user_did}"
        # Retrieve relevant memories via vector similarity
        
    async def store_interaction(self, user_did: str, interaction):
        # Embed and store in user namespace
        
    async def search_archival(self, query: str):
        # Search across all namespaces
```

### 3. Agent Architecture (Inspired by Marvin)

#### Multi-Agent System
```python
class BotAgent:
    """Main conversational agent"""
    
    async def respond(self, context: UserContext) -> Response:
        # Decide if delegation needed
        if needs_research:
            return await self.research_agent.investigate(query)
        return await self.generate_response(context)

class ResearchAgent:
    """Specialized for information gathering"""
    
    async def investigate(self, query: str) -> Finding:
        # Web search, memory search, etc.
```

### 4. Safety & Interaction Model (Inspired by Penelope)

#### Opt-In Only
- Only respond to direct mentions
- Admin whitelist for testing phase
- Rate limiting per user

#### Self-Modification Capabilities
- Update own profile (like Penelope)
- Modify display name based on identity
- Store changes in core memory

#### Error Handling
```python
class SafeMessageHandler:
    async def handle_mention(self, notification):
        try:
            with timeout(30):  # Max processing time
                response = await self.process(notification)
                await self.publish(response)
        except Exception as e:
            logger.error(f"Failed to process: {e}")
            # Don't crash, just log
```

### 5. Conversation Management

#### Context Building
1. Load thread history (like Penelope)
2. Retrieve user memories (like Void)
3. Apply conversation summarization (like Marvin)
4. Inject into LLM prompt

#### Progress Updates (from Marvin)
```python
@contextmanager
def track_progress(handler):
    """Send typing indicators or progress messages"""
    # Start typing indicator
    yield
    # Stop typing indicator
```

## Key Design Decisions

### 1. Memory Strategy
- **TurboPuffer** for scalable vector storage
- **Namespaces** for user isolation
- **Embeddings** for semantic retrieval
- **Hybrid search** (vector + keyword)

### 2. Personality Consistency
- **Immutable core prompt** (like Void)
- **Personality reinforcement** in every interaction
- **Admin-only modifications**
- **Character guidelines** in core memory

### 3. Scaling Approach
- **Async everything** (FastAPI lifespan)
- **User-specific namespaces** (no cross-contamination)
- **Queue-based processing** (handle bursts)
- **Cursor persistence** (resume after crashes)

### 4. LLM Integration
- **pydantic-ai** for structured outputs
- **Tool calling** for actions
- **Context injection** for memory
- **Token management** for cost control

## Deployment Architecture

### Remote GPU Setup (Like Penelope)
```
┌─────────────┐     HTTPS/WSS      ┌──────────────┐
│   FastAPI   │ ◄─────────────► │ GPU Machine  │
│   Bot App   │                   │ - LLM API    │
└─────────────┘                   │ - Embedding  │
                                  └──────────────┘
```

### Considerations
- Use Tailscale/VPN for secure remote access
- Handle HTTPS properly (avoid mixed content)
- Consider GPU for heavy LLM/embedding tasks
- Separate compute from bot logic

## Implementation Priorities

1. **Phase 1: Basic Bot**
   - Simple replies with pydantic-ai
   - Basic memory storage
   - Admin-only interactions

2. **Phase 2: Memory System**
   - TurboPuffer integration
   - User context loading
   - Conversation history

3. **Phase 3: Advanced Features**
   - Multi-agent delegation
   - Tool calling (search, etc.)
   - Personality refinement

4. **Phase 4: Public Release**
   - Remove admin restrictions
   - Add rate limiting
   - Monitor and iterate

## Unique Features to Consider

1. **"Void-style" Transparency**
   - Public reasoning traces
   - Memory inspection endpoint
   - Open source code

2. **"Marvin-style" Progress**
   - Real-time updates during processing
   - Usage statistics
   - Performance monitoring

3. **"Penelope-style" Features**
   - Strict opt-in model
   - Graceful error handling
   - AT Protocol compliance
   - Self-profile updates
   - Core memory for identity

## Next Steps
1. Add pydantic-ai and turbopuffer to dependencies
2. Implement basic LLM agent
3. Design personality and prompts
4. Build memory manager
5. Test with admin interactions