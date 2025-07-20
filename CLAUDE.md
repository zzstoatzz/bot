This is the repository for a bluesky virtual person powered by LLMs and exposed to the web.

This is a python project that uses `uv` as python package manager, `fastapi` and is inspired by `https://tangled.sh/@cameron.pfiffer.org/void`, `https://github.com/haileyok/penelope`, and `https://github.com/PrefectHQ/marvin/tree/main/examples/slackbot` (tangled is github on atproto, you can git clone tangled.sh repos). These projects should be cloned to the `.eggs` directory, along with any other resources that are useful but not worth checking into the repo. We should simply common commands and communicate dev workflows by using a `justfile`.

Work from repo root whenever possible.

## Project Structure

- `src/bot/` - Main bot application code
  - `core/` - Core functionality (AT Protocol client, response generation)
  - `services/` - Services (notification polling, message handling)
  - `config.py` - Configuration using pydantic-settings
  - `main.py` - FastAPI application entry point
- `tests/` - Test files
- `scripts/` - Utility scripts (test_post.py, test_mention.py)
- `sandbox/` - Documentation and analysis
  - Reference project analyses
  - Architecture plans
  - Implementation notes
- `.eggs/` - Cloned reference projects (void, penelope, marvin)

## Current State

The bot has a working placeholder implementation that:
- Authenticates with Bluesky using app password
- Polls for mentions every 10 seconds
- Responds with random placeholder messages
- Properly marks notifications as read

## Key Implementation Details

### Notification Handling
The bot uses Void's approach: capture timestamp BEFORE fetching notifications, then mark as seen using that timestamp. This prevents missing notifications that arrive during processing.

### Response System
Uses a Protocol-based ResponseGenerator that's easy to swap:
- `PlaceholderResponseGenerator` - Current random messages
- `LLMResponseGenerator` - Future pydantic-ai implementation

### Next Steps
1. Add TurboPuffer for memory
2. Implement LLM-based responses
3. Add memory context to responses
4. Design bot personality

## Testing
- Run bot: `just dev`
- Test posting: `just test-post`
- Test mentions: Need TEST_BLUESKY_HANDLE in .env, then mention @zzstoatzz.bsky.social