# Project Status

## Current Phase: Placeholder Bot Complete ✅

### Completed
- ✅ Created project directory structure (.eggs, tests, sandbox)
- ✅ Cloned reference projects:
  - penelope (Go bot with self-modification capabilities)
  - void (Python/Letta with sophisticated 3-tier memory)
  - marvin/slackbot (Multi-agent with TurboPuffer)
- ✅ Deep analysis of all reference projects (see sandbox/)
- ✅ Basic bot infrastructure working:
  - FastAPI with async lifespan management
  - AT Protocol authentication and API calls
  - Notification polling (10 second intervals)
  - Placeholder response system
  - Graceful shutdown for hot reloading
- ✅ Notification handling using Void's timestamp approach
- ✅ Test scripts for posting and mentions

### Current Implementation Details
- Bot responds to mentions with random placeholder messages
- Uses `atproto` Python SDK with proper authentication
- Notification marking captures timestamp BEFORE fetching (avoids duplicates)
- Local URI cache (`_processed_uris`) as safety net
- No @mention in replies (Bluesky handles notification automatically)

### Current Focus: AI Responses with Thread Context

The immediate goal is to get AI responses working with full thread history in context. This means:

1. **Thread History** - Store and retrieve conversation history per thread
   - SQLite for simple thread storage (like Marvin)
   - Pass full thread context to AI
   
2. **AI Integration** - Working Anthropic responses with personality
   - ✅ Basic pydantic-ai integration 
   - ✅ Personality loaded from markdown
   - 🚧 Thread-aware responses
   
3. **Better DX** - Learn from Marvin's patterns
   - Dynamic system prompts with context
   - Clean agent/tool architecture

### Future Work

After thread context is working:
- TurboPuffer for vector memory (user facts, etc)
- Self-modification capabilities
- Multi-tier memory system

## Key Decisions to Make
- Which LLM provider to use (OpenAI, Anthropic, etc.)
- Bot personality and behavior design
- Hosting and deployment strategy
- Response generation approach (streaming vs batch)

## Reference Projects Analysis
- **penelope**: Go-based with core memory, self-modification, and Google search capabilities
- **void**: Python/Letta with sophisticated 3-tier memory and strong personality consistency
- **marvin slackbot**: Multi-agent architecture with TurboPuffer vector memory and progress tracking

### Key Insights from Deep Dive
- All three bots have memory systems (not just Void)
- Penelope can update its own profile and has "core memory"
- Marvin uses user-namespaced vectors in TurboPuffer
- Deployment often involves separate GPU machines for LLM
- HTTPS/CORS handling is critical for remote deployments