This is the repository for a bluesky virtual person powered by LLMs and exposed to the web.

This is a python project that uses `uv` as python package manager, `fastapi` and is inspired by `https://tangled.sh/@cameron.pfiffer.org/void`, `https://github.com/haileyok/penelope`, and `https://github.com/PrefectHQ/marvin/tree/main/examples/slackbot` (tangled is github on atproto, you can git clone tangled.sh repos). These projects should be cloned to the `.eggs` directory, along with any other resources that are useful but not worth checking into the repo. We should simply common commands and communicate dev workflows by using a `justfile`.

Work from repo root whenever possible.

## Python style
- 3.10+ and complete typing (T | None preferred over Optional[T] and list[T] over typing.List[T])
- use prefer functional over OOP
- keep implementation details private and functions pure
- never use `pytest.mark.asyncio`, its unnecessary

## Project Structure

- `src/bot/` - Main bot application code
  - `agents/` - Agents for the LLM
  - `core/` - Core functionality (AT Protocol client functionality)
  - `services/` - Services (notification polling, message handling)
  - `tools/` - Tools for the LLM
  - `config.py` - Configuration
  - `database.py` - Database functionality
  - `main.py` - FastAPI application entry point
  - `personality.py` - Personality definition
  - `response_generator.py` - Response generation
  - `status.py` - One page status tracker
  - `templates.py` - HTML templates

- `tests/` - Test files
- `scripts/` - Curated utility scripts that have proven useful
- `sandbox/` - Proving ground for experiments, analysis, and unproven scripts
  - Reference project analyses
  - Architecture plans
  - Implementation notes
  - Experimental scripts (graduate to scripts/ once proven useful)
- `.eggs/` - Cloned reference projects (void, penelope, marvin)

## Script Graduation Process
New scripts start in `sandbox/`, get promoted to `scripts/` once proven useful, and may eventually get just commands added if the workflow should be broadcast to other developers. Not everything graduates - most things stay in sandbox.

## Testing
- Run bot: `just dev`
- Test posting: `just test-post`

## Important Development Guidelines
- STOP DEFERRING IMPORTS. Put all imports at the top of the file unless there's a legitimate circular dependency issue. Deferred imports make code harder to understand and debug.