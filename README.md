# Bluesky Bot

A virtual person for Bluesky powered by LLMs, built with FastAPI and pydantic-ai.

## Quick Start

Get your bot running in 5 minutes:

```bash
# Clone and install
git clone <repo>
cd bot
uv sync

# Configure (copy .env.example and add your credentials)
cp .env.example .env

# Run the bot
just dev
```

That's it! Your bot is now listening for mentions.

## Configuration

Edit `.env` with your credentials:
- `BLUESKY_HANDLE`: Your bot's Bluesky handle
- `BLUESKY_PASSWORD`: App password (not your main password!)
- `ANTHROPIC_API_KEY`: Your Anthropic key for AI responses
- `TURBOPUFFER_API_KEY`: Your TurboPuffer key for memory storage
- `OPENAI_API_KEY`: Your OpenAI key for embeddings (memory system)
- `BOT_NAME`: Your bot's name (default: "Bot")
- `PERSONALITY_FILE`: Path to personality markdown file (default: "personalities/phi.md")

## Current Features

- ✅ Responds to mentions with AI-powered messages
- ✅ Proper notification handling (no duplicates)
- ✅ Graceful shutdown for hot-reload  
- ✅ AI integration with Anthropic Claude
- ✅ Thread-aware responses with full conversation context
- ✅ Status page at `/status` showing activity and health
- ✅ Web search capability (Google Custom Search API)
- ✅ Content moderation with philosophical responses
- ✅ Namespace-based memory system with TurboPuffer
- ✅ Online/offline status in bio
- 🚧 Self-modification capabilities (planned)

## Architecture

- **FastAPI** web framework with async support
- **pydantic-ai** for LLM agent management  
- **TurboPuffer** for scalable vector memory
- **AT Protocol** for Bluesky integration
- **SQLite** for thread context storage

## Development

```bash
just           # Show available commands
just dev       # Run with hot-reload
just test-post # Test posting capabilities
just test-thread # Test thread context database
just test-search # Test web search
just test-agent-search # Test agent with search capability
just fmt       # Format code
just status    # Check project status
just test      # Run all tests

# Memory management
uv run scripts/init_core_memories.py      # Initialize core memories from personality
uv run scripts/check_memory.py            # View current memory state
uv run scripts/migrate_creator_memories.py # Migrate creator conversations
```

### Status Page

Visit http://localhost:8000/status while the bot is running to see:
- Current bot status and uptime
- Mentions received and responses sent
- AI mode (enabled/placeholder)
- Last activity timestamps
- Error count

## Personality System

The bot's personality is defined in markdown files in the `personalities/` directory. This allows for rich, detailed personality definitions that shape how the bot communicates.

- See `personalities/phi.md` for an example exploring consciousness
- See `personalities/default.md` for a simple assistant
- Create your own by adding a `.md` file and setting `PERSONALITY_FILE` in `.env`

## Tools & Capabilities

### Web Search
The bot can search the web when configured with Google Custom Search API credentials. Add to `.env`:
- `GOOGLE_API_KEY`: Your Google API key
- `GOOGLE_SEARCH_ENGINE_ID`: Your custom search engine ID

### Content Moderation
Built-in moderation filters:
- Spam detection (excessive caps, repetition, promotional content)
- Harassment and hate speech filtering
- Violence and threatening content detection
- Consistent philosophical responses to moderated content

## Memory System

The bot uses a namespace-based memory architecture with TurboPuffer:

- **Core Memory** (`phi-core`): Personality, guidelines, and capabilities loaded from personality files
- **User Memory** (`phi-users-{handle}`): Per-user conversation history and facts

Key features:
- Vector embeddings using OpenAI's text-embedding-3-small
- Automatic context assembly for conversations
- Character limits to prevent token overflow
- User isolation through separate namespaces

See `docs/memory-architecture.md` for detailed documentation.

## Troubleshooting

**Bot gives placeholder responses?**
- Check your `ANTHROPIC_API_KEY` is set correctly
- Restart the bot after changing `.env`

**Not seeing mentions?**
- Verify your `BLUESKY_HANDLE` and `BLUESKY_PASSWORD`
- Make sure you're using an app password, not your main password

## Project Structure

```
bot/
├── src/bot/          # Main application code
│   ├── agents/       # AI agent implementations
│   ├── core/         # AT Protocol client and profile management
│   ├── memory/       # TurboPuffer namespace memory system
│   ├── services/     # Notification polling and message handling
│   ├── tools/        # Google search tool
│   └── main.py       # FastAPI application entry
├── scripts/          # Utility scripts
│   ├── test_bot.py   # Unified testing script (post, mention, search, thread)
│   └── manage_memory.py # Memory management (init, check, migrate)
├── personalities/    # Bot personality definitions
├── docs/            # Architecture documentation
├── sandbox/         # Reference project analysis
└── tests/           # Test suite
```

## Reference Projects

Inspired by [Void](https://tangled.sh/@cameron.pfiffer.org/void.git), [Penelope](https://github.com/haileyok/penelope), and [Marvin](https://github.com/PrefectHQ/marvin). See `sandbox/REFERENCE_PROJECTS.md` for details.