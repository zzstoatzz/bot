# Run the bot with hot-reload
dev:
    uv run uvicorn src.bot.main:app --reload

# Test posting capabilities  
test-post:
    uv run python scripts/test_post.py

# Test thread context
test-thread:
    uv run python scripts/test_thread_context.py

# Run tests
test:
    uv run pytest tests/ -v

# Format code
fmt:
    uv run ruff format src/ scripts/ tests/

# Lint code
lint:
    uv run ruff check src/ scripts/ tests/

# Type check with ty
typecheck:
    uv run ty check

# Run all checks
check: lint typecheck test