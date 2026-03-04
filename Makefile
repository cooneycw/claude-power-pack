.PHONY: test lint format clean

## Quality gates (used by /flow:finish)

lint:
	uv run --extra dev ruff check .

format:
	uv run --extra dev ruff format .

test:
	uv run --extra dev pytest

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
