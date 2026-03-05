.PHONY: test lint format typecheck verify update_docs clean \
       docker-build docker-up docker-down docker-logs docker-ps

## Quality gates (used by /flow:finish)

lint:
	uv run --extra dev ruff check .

format:
	uv run --extra dev ruff format .

test:
	uv run --extra dev pytest

typecheck:
	uv run --extra dev mypy .

## Pre-deploy gate (runs all quality checks)

verify: lint test typecheck

## Documentation (used by /flow:auto and /flow:finish)

update_docs:
	@echo "Run /documentation:c4 to regenerate C4 architecture diagrams"
	@echo "Review CLAUDE.md and README.md for accuracy"

## Docker (MCP server containers)
## Usage: make docker-up PROFILE=core
##        make docker-up PROFILE="core browser"
## Profiles: core (second-opinion + nano-banana), browser, coord

PROFILE ?= core

docker-build:
	$(foreach p,$(PROFILE),docker compose --profile $(p) build;)

docker-up:
	$(foreach p,$(PROFILE),docker compose --profile $(p) up -d;)

docker-down:
	docker compose --profile core --profile eval --profile browser --profile coord down

docker-logs:
	docker compose --profile core --profile eval --profile browser --profile coord logs -f

docker-ps:
	docker compose --profile core --profile eval --profile browser --profile coord ps

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
