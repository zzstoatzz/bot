# Quick Start Guide

Get your Bluesky bot running in 5 minutes!

## Prerequisites

- Python 3.12+
- A Bluesky account
- An Anthropic API key (for AI responses)

## Setup

1. **Clone and install:**
```bash
git clone <repo>
cd bot
uv sync
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your credentials:
# - BLUESKY_HANDLE: Your bot's handle
# - BLUESKY_PASSWORD: App password (not your main password!)
# - ANTHROPIC_API_KEY: Your Anthropic key
```

3. **Run the bot:**
```bash
just dev
```

That's it! Your bot is now listening for mentions.

## Test It Out

1. From another Bluesky account, mention your bot
2. Watch the terminal - you'll see the mention come in
3. The bot will respond based on its personality

## Customize

- Edit `personalities/phi.md` to change how your bot thinks and speaks
- Or create a new personality file and update `PERSONALITY_FILE` in `.env`

## Monitoring

Visit http://localhost:8000/status to see:
- Bot status and uptime
- Mentions and responses count
- Current mode (AI or placeholder)

## Troubleshooting

**Bot gives placeholder responses?**
- Check your `ANTHROPIC_API_KEY` is set correctly
- Restart the bot after changing `.env`

**Not seeing mentions?**
- Verify your `BLUESKY_HANDLE` and `BLUESKY_PASSWORD`
- Make sure you're using an app password, not your main password