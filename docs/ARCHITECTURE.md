# Architecture Overview

## Core Components

### 1. Notification Polling (`notification_poller.py`)
- Polls Bluesky every 10 seconds for new notifications
- Uses Void's timestamp approach to prevent duplicates
- Runs as async task in FastAPI lifespan

### 2. Message Handling (`message_handler.py`) 
- Processes mentions from notifications
- Stores messages in thread database
- Generates responses with full thread context
- Creates proper AT Protocol reply structures

### 3. Response Generation (`response_generator.py`)
- Factory pattern for AI or placeholder responses
- Loads Anthropic agent when API key present
- Falls back gracefully to placeholder messages

### 4. Thread Database (`database.py`)
- SQLite storage for conversation threads
- Tracks by root URI for proper threading
- Stores all messages with author info
- Provides formatted context for AI

### 5. AI Agent (`agents/anthropic_agent.py`)
- Uses pydantic-ai with Anthropic Claude
- Loads personality from markdown files
- Includes thread context in prompts
- Enforces 300 character limit

## Data Flow

1. **Notification arrives** → Poller detects it
2. **Message handler** → Extracts post data, stores in DB
3. **Thread context** → Retrieved from database
4. **AI generation** → Personality + context → response
5. **Reply posted** → Proper threading maintained
6. **Response stored** → For future context

## Key Design Decisions

- **SQLite for threads**: Simple, effective (like Marvin)
- **Personality as markdown**: Rich, versionable definitions
- **Timestamp-first polling**: Prevents missing notifications
- **Factory pattern**: Clean AI/placeholder switching
- **Thread tracking by root**: Handles nested conversations