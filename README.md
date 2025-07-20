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
- `BOT_NAME`: Your bot's name (default: "Bot")
- `PERSONALITY_FILE`: Path to personality markdown file (default: "personalities/phi.md")

## Current Features

- ✅ Responds to mentions with placeholder or AI messages
- ✅ Proper notification handling (no duplicates)
- ✅ Graceful shutdown for hot-reload
- ✅ AI integration with Anthropic Claude (when API key provided)
- ✅ Thread-aware responses with full conversation context
- ✅ Status page at `/status` showing activity and health
- 🚧 Memory system (coming soon)
- 🚧 Self-modification capabilities (planned)

## Architecture

- **FastAPI** web framework with async support
- **pydantic-ai** for LLM agent management
- **TurboPuffer** for scalable vector memory (planned)
- **AT Protocol** for Bluesky integration

## Development

```bash
just           # Show available commands
just dev       # Run with hot-reload
just test-post # Test posting capabilities
just test-thread # Test thread context database
just fmt       # Format code
just status    # Check project status
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

## Memory Architecture

See `sandbox/memory_architecture_plan.md` for the planned memory system using TurboPuffer.

## Troubleshooting

**Bot gives placeholder responses?**
- Check your `ANTHROPIC_API_KEY` is set correctly
- Restart the bot after changing `.env`

**Not seeing mentions?**
- Verify your `BLUESKY_HANDLE` and `BLUESKY_PASSWORD`
- Make sure you're using an app password, not your main password

## Reference Projects

This bot is inspired by:
- **Void** by Cameron Pfiffer - Sophisticated memory system
- **Penelope** by Hailey - Self-modifying capabilities
- **Marvin Slackbot** - Multi-agent architecture

See `sandbox/` for detailed analysis of each project.