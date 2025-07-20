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
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`: For LLM responses

3. Test posting:
```bash
just test-post
```

4. Run the bot:
```bash
just dev
```

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

## Memory Architecture

See `sandbox/memory_architecture_plan.md` for the planned memory system using TurboPuffer.

## Reference Projects

This bot is inspired by:
- **Void** by Cameron Pfiffer - Sophisticated memory system
- **Penelope** by Hailey - Self-modifying capabilities
- **Marvin Slackbot** - Multi-agent architecture

See `sandbox/` for detailed analysis of each project.