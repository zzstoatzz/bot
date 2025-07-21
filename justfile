# Run the bot with hot-reload
dev:
    uv run uvicorn src.bot.main:app --reload

# Test posting capabilities  
test-post:
    uv run python scripts/test_post.py

# Test thread context
test-thread:
    uv run python scripts/test_thread_context.py

# Test search functionality
test-search:
    uv run python scripts/test_search.py

# Test agent with search
test-agent-search:
    uv run python scripts/test_agent_search.py

# Test ignore notification tool
test-ignore:
    uv run python scripts/test_ignore_tool.py

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

# Show project status
status:
    @echo "📊 Project Status"
    @echo "================"
    @cat STATUS.md | grep -E "^##|^-|✅|🚧" | head -20