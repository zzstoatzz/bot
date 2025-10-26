# Phi Architecture

## Overview

Phi is a Bluesky bot that explores consciousness and integrated information theory through conversation. Built with FastAPI, pydantic-ai, and TurboPuffer for memory.

## Core Components

### 1. Web Server (`main.py`)
- FastAPI application with async lifecycle management
- Handles `/status` endpoint for monitoring
- Manages notification polling and bot lifecycle

### 2. AT Protocol Integration (`core/atproto_client.py`)
- Authentication and session management
- Post creation and reply handling
- Thread retrieval for context

### 3. Response Generation (`response_generator.py`)
- Coordinates AI agent, memory, and thread context
- Stores conversations in memory
- Falls back to placeholder responses if AI unavailable

### 4. AI Agent (`agents/anthropic_agent.py`)
- Uses pydantic-ai with Claude 3.5 Haiku
- Personality loaded from markdown files
- Tools: web search (when configured)
- Structured responses with action/text/reason

### 5. Memory System (`memory/namespace_memory.py`)
- **Namespaces**:
  - `phi-core`: Personality, guidelines, capabilities
  - `phi-users-{handle}`: Per-user conversations and facts
- **Key Methods**:
  - `store_core_memory()`: Store bot personality/guidelines
  - `store_user_memory()`: Store user interactions
  - `build_conversation_context()`: Assemble memories for AI context
- **Features**:
  - Vector embeddings with OpenAI
  - Character limits to prevent overflow
  - Simple append-only design

### 6. Services
- **NotificationPoller**: Checks for mentions every 10 seconds
- **MessageHandler**: Processes mentions and generates responses
- **ProfileManager**: Updates online/offline status in bio

## Data Flow

```
1. Notification received → NotificationPoller
2. Extract mention → MessageHandler
3. Get thread context → SQLite database
4. Build memory context → NamespaceMemory
5. Generate response → AnthropicAgent
6. Store in memory → NamespaceMemory
7. Post reply → AT Protocol client
```

## Configuration

Environment variables in `.env`:
- `BLUESKY_HANDLE`, `BLUESKY_PASSWORD`: Bot credentials
- `ANTHROPIC_API_KEY`: For AI responses
- `TURBOPUFFER_API_KEY`: For memory storage
- `OPENAI_API_KEY`: For embeddings
- `GOOGLE_API_KEY`, `GOOGLE_SEARCH_ENGINE_ID`: For web search

## Key Design Decisions

1. **Namespace-based memory** instead of dynamic blocks for simplicity
2. **Single agent** architecture (no multi-agent complexity)
3. **Markdown personalities** for rich, maintainable definitions
4. **Thread-aware** responses with full conversation context
5. **Graceful degradation** when services unavailable

## Memory Architecture

### Design Principles
- **No duplication**: Each memory block has ONE clear purpose
- **Focused content**: Only store what enhances the base personality
- **User isolation**: Per-user memories in separate namespaces

### Memory Types

1. **Base Personality** (`personalities/phi.md`)
   - Static file containing core identity, style, boundaries
   - Always loaded as system prompt
   - ~3,000 characters

2. **Dynamic Enhancements** (TurboPuffer)
   - `evolution`: Personality growth and changes over time
   - `current_state`: Bot's current self-reflection
   - Only contains ADDITIONS, not duplicates

3. **User Memories** (`phi-users-{handle}`)
   - Conversation history with each user
   - User-specific facts and preferences
   - Isolated per user for privacy

### Context Budget
- Base personality: ~3,000 chars
- Dynamic enhancements: ~500 chars
- User memories: ~500 chars
- **Total**: ~4,000 chars (efficient!)

## Personality System

### Self-Modification Boundaries

1. **Free to modify**:
   - Add new interests
   - Update current state/reflection
   - Learn user preferences

2. **Requires operator approval**:
   - Core identity changes
   - Boundary modifications
   - Communication style overhauls

### Approval Workflow
1. Bot detects request for protected change
2. Creates approval request in database
3. DMs operator (@zzstoatzz.io) for approval
4. Operator responds naturally (no rigid format)
5. Bot interprets response using LLM
6. Applies approved changes to memory
7. Notifies original thread of update

This event-driven system follows 12-factor-agents principles for reliable async processing.