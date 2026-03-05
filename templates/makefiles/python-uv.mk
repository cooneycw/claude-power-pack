# Makefile — Python + uv (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# All commands use `uv run` for dependency isolation.
# Copy to your project root as "Makefile" and customize.

.PHONY: lint test typecheck format build deploy clean verify troubleshoot ci-local

## Quality gates (used by /flow:finish)

lint:
	uv run ruff check .

test:
	uv run pytest

## Recommended targets

typecheck:
	uv run mypy .

format:
	uv run ruff format .

build:
	uv build

## Pre-deploy gate (runs all quality checks)

verify: lint test typecheck

## Deployment (used by /flow:deploy)

deploy: verify
	@echo "TODO: Define your deploy steps here"
	@echo "Examples:"
	@echo "  ssh prod 'cd /app && git pull && systemctl restart app'"
	@echo "  docker compose up -d --build"

## Troubleshooting (single-command diagnostic pass)

troubleshoot: clean lint test
	@echo "All checks passed — issue may be environmental"

## Local CI (requires: woodpecker-cli — https://woodpecker-ci.org/)

ci-local:
	woodpecker exec

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info .venv
