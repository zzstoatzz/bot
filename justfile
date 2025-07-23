# Core development commands
dev:
    uv run uvicorn src.bot.main:app --reload

test:
    uv run pytest tests/ -v

fmt:
    uv run ruff format src/ scripts/ tests/

lint:
    uv run ruff check src/ scripts/ tests/

check: lint test

# Bot testing utilities
test-post:
    uv run python scripts/test_bot.py post

test-mention:
    uv run python scripts/test_bot.py mention

test-search:
    uv run python scripts/test_bot.py search

test-thread:
    uv run python scripts/test_bot.py thread

test-like:
    uv run python scripts/test_bot.py like

test-non-response:
    uv run python scripts/test_bot.py non-response

test-dm:
    uv run python scripts/test_bot.py dm

test-dm-check:
    uv run python scripts/test_bot.py dm-check

# Memory management
memory-init:
    uv run python scripts/manage_memory.py init

memory-check:
    uv run python scripts/manage_memory.py check

memory-migrate:
    uv run python scripts/manage_memory.py migrate

# Setup reference projects
setup:
    @mkdir -p .eggs
    @[ -d .eggs/void ] || git clone https://tangled.sh/@cameron.pfiffer.org/void.git .eggs/void
    @[ -d .eggs/penelope ] || git clone https://github.com/haileyok/penelope.git .eggs/penelope
    @[ -d .eggs/marvin ] || git clone https://github.com/PrefectHQ/marvin.git .eggs/marvin