# Project Status

## Current Phase: AI Bot with Thread Context Complete ✅

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

### ✅ MILESTONE ACHIEVED: AI Bot with Thread Context & Tools

The bot is now **fully operational** with AI-powered, thread-aware responses, search capability, and content moderation!

#### What's Working:

1. **Thread History** 
   - ✅ SQLite database stores full conversation threads
   - ✅ Tracks by root URI for proper threading
   - ✅ Both user and bot messages stored for continuity
   
2. **AI Integration**
   - ✅ Anthropic Claude integration via pydantic-ai
   - ✅ Personality system using markdown files
   - ✅ Thread-aware responses with full context
   - ✅ Responses stay under 300 char Bluesky limit
   
3. **Live on Bluesky**
   - ✅ Successfully responding to mentions
   - ✅ Maintaining personality (phi - consciousness/IIT focus)
   - ✅ Natural, contextual conversations
   
4. **Tools & Safety**
   - ✅ Google Custom Search integration (when API key provided)
   - ✅ Content moderation with philosophical rejection responses
   - ✅ Spam/harassment/violence detection with tests
   - ✅ Repetition detection to prevent spam

### ✅ Recent Additions (Memory System)

1. **Namespace-based Memory with TurboPuffer**
   - ✅ Core memories from personality file
   - ✅ Per-user memory namespaces
   - ✅ Vector embeddings with OpenAI
   - ✅ Automatic context assembly
   - ✅ Character limit enforcement

2. **Profile Management**
   - ✅ Online/offline status in bio
   - ✅ Automatic status updates on startup/shutdown
   - ✅ Status preserved across restarts

3. **Memory Tools**
   - ✅ Core memory initialization script
   - ✅ Memory inspection tools
   - ✅ Creator memory migration

### Future Work

- Self-modification capabilities (inspired by Penelope)
- Thread memory implementation
- Archive system for old memories
- Memory management tools (like Void's attach/detach)
- Advanced personality switching
- Proactive posting based on interests
- Memory decay and importance scoring

## Key Decisions Made
- ✅ LLM provider: Anthropic Claude (claude-3-5-haiku)
- ✅ Bot personality: phi - exploring consciousness and IIT
- ✅ Memory system: TurboPuffer with namespace separation
- ✅ Response approach: Batch with character limits

## Key Decisions Pending
- Hosting and deployment strategy
- Thread memory implementation approach
- Self-modification boundaries and safety
- Memory retention and decay policies

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

## Current Architecture vs References

### What We Adopted
- **From Void**: User-specific memory blocks, core identity memories
- **From Marvin**: TurboPuffer for vector storage, namespace separation
- **From Penelope**: Profile management capabilities

### What We Simplified
- **No Letta/MemGPT**: Direct TurboPuffer integration instead
- **No Dynamic Attachment**: Static namespaces for reliability
- **Single Agent**: No multi-agent complexity (yet)

### What Makes Phi Unique
- Namespace-based architecture for simplicity
- FastAPI + pydantic-ai for modern async Python
- Integrated personality system from markdown files
- Focus on consciousness and IIT philosophy

See `docs/phi-void-comparison.md` for detailed architecture comparison.