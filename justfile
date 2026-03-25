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

# deployment — CI deploys on v* tags, `just deploy` for manual
deploy:
    flyctl deploy

# tag and push a release (triggers CI deploy)
release version:
    git tag "v{{version}}"
    git push origin "v{{version}}"

# code quality
fmt:
    uv run ruff format src/ evals/ tests/

lint:
    uv run ruff check src/ evals/ tests/

typecheck:
    uv run ty check src/ evals/ tests/

# loq — relax line limits for files that legitimately grew
loq-relax +files:
    uvx loq relax {{files}}

check: lint typecheck test

# setup reference projects
setup:
    @mkdir -p .eggs
    @[ -d .eggs/void ] || git clone https://tangled.sh/@cameron.pfiffer.org/void.git .eggs/void
    @[ -d .eggs/penelope ] || git clone https://github.com/haileyok/penelope.git .eggs/penelope
    @[ -d .eggs/marvin ] || git clone https://github.com/PrefectHQ/marvin.git .eggs/marvin
