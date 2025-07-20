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

### Near-Term Roadmap

#### Phase 1: AI Integration (Current Focus)
1. **Add pydantic-ai with Anthropic provider**
   - Use Anthropic as the LLM provider (Mac subscription available)
   - Redesign ResponseGenerator protocol to be more general/sensible
   - Implement AI-based response generation
   
2. **Self-Modification Capability** 
   - Build in ability to edit own personality/profile from the start
   - Similar to Void's self-editing and Penelope's profile updates
   - Essential foundation before adding memory systems

#### Phase 2: Memory & Persistence
1. Add turbopuffer for vector memory
2. Build 3-tier memory system (like Void)
3. User-specific memory contexts

#### Phase 3: Personality & Behavior
1. Design bot persona and system prompts
2. Implement conversation styles
3. Add behavioral consistency

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