# run phi
dev:
    uv run uvicorn src.bot.main:app --reload

run:
    uv run uvicorn src.bot.main:app

# testing
test:
    uv run pytest tests/ -v

evals:
    uv run pytest evals/ -v

evals-basic:
    uv run pytest evals/test_basic_responses.py -v

evals-memory:
    uv run pytest evals/test_memory_integration.py -v

# code quality
fmt:
    uv run ruff format src/ evals/ tests/

lint:
    uv run ruff check src/ evals/ tests/

typecheck:
    uv run ty check src/ evals/ tests/

check: lint typecheck test

# view phi's activity
view-posts:
    uv run --with rich --with httpx python scripts/view_phi_posts.py

view-thread URI:
    uv run --with rich --with httpx python scripts/view_thread.py {{URI}}

# setup reference projects
setup:
    @mkdir -p .eggs
    @[ -d .eggs/void ] || git clone https://tangled.sh/@cameron.pfiffer.org/void.git .eggs/void
    @[ -d .eggs/penelope ] || git clone https://github.com/haileyok/penelope.git .eggs/penelope
    @[ -d .eggs/marvin ] || git clone https://github.com/PrefectHQ/marvin.git .eggs/marvin
