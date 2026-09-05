# Makefile — Python + pip (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# Uses pip with a virtual environment bootstrapped by `uv venv`. Activate your
# venv first, or adjust commands to use `python -m` prefix.
# Copy to your project root as "Makefile" and customize.

.PHONY: lint test typecheck format build deploy clean verify troubleshoot venv venv-stdlib ci-local

## Quality gates (used by /flow:finish)

lint:
	python -m ruff check .

test:
	python -m pytest

## Recommended targets

typecheck:
	python -m mypy .

format:
	python -m ruff format .

build:
	python -m build

## Virtual environment setup

# `uv` is already a CPP prerequisite, so it is present wherever CPP works.
# Debian/Ubuntu split ensurepip into python3-venv; a stdlib failure can leave a
# half-built .venv without pip.
venv:
	uv venv .venv
	uv pip install -r requirements.txt

# Stdlib fallback: Debian/Ubuntu require `apt install python3-venv`.
venv-stdlib:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt

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
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
