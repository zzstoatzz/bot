# Bluesky Bot

A virtual person for Bluesky powered by LLMs, built with FastAPI and pydantic-ai.

## Setup

1. Install dependencies:
```bash
just sync
```

2. Copy `.env.example` to `.env` and add your credentials:
- `BLUESKY_HANDLE`: Your bot's Bluesky handle
- `BLUESKY_PASSWORD`: App password from Bluesky settings
- `ANTHROPIC_API_KEY`: For AI responses (optional, falls back to placeholder)

3. Test posting:
```bash
just test-post
```

4. Run the bot:
```bash
just dev
```

## Current Features

- ✅ Responds to mentions with placeholder or AI messages
- ✅ Proper notification handling (no duplicates)
- ✅ Graceful shutdown for hot-reload
- ✅ AI integration with Anthropic Claude (when API key provided)
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

## Memory Architecture

See `sandbox/memory_architecture_plan.md` for the planned memory system using TurboPuffer.

## Reference Projects

This bot is inspired by:
- **Void** by Cameron Pfiffer - Sophisticated memory system
- **Penelope** by Hailey - Self-modifying capabilities
- **Marvin Slackbot** - Multi-agent architecture

See `sandbox/` for detailed analysis of each project.