.PHONY: test lint format typecheck verify update_docs clean \
       docker-build docker-check-env docker-up docker-down docker-logs docker-ps

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

docker-check-env:
	@if [ ! -f .env ]; then \
		echo ""; \
		echo "WARNING: .env file not found in $$(pwd)"; \
		echo "Docker containers will start WITHOUT API keys."; \
		echo "MCP Second Opinion will report 'no_api_keys' status."; \
		echo ""; \
		echo "Create .env with at least one key:"; \
		echo "  echo 'GEMINI_API_KEY=your-key' > .env"; \
		echo ""; \
		echo "Or run /cpp:init to configure interactively."; \
		echo ""; \
	elif ! grep -qE '^(GEMINI|OPENAI|ANTHROPIC)_API_KEY=.+' .env 2>/dev/null; then \
		echo ""; \
		echo "WARNING: .env exists but contains no API keys."; \
		echo "Add at least one: GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY"; \
		echo ""; \
	fi

docker-up: docker-check-env
	$(foreach p,$(PROFILE),docker compose --profile $(p) up -d;)

docker-down:
	docker compose --profile core --profile browser --profile coord down

docker-logs:
	docker compose --profile core --profile browser --profile coord logs -f

docker-ps:
	docker compose --profile core --profile browser --profile coord ps

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
