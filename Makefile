.PHONY: test lint format typecheck verify clean

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

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
