# Makefile — Django + uv (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# All commands use `uv run` for dependency isolation.
# Copy to your project root as "Makefile" and customize.
#
# Django-specific targets: migrate, collectstatic, runserver, shell, createsuperuser

.PHONY: lint test typecheck format build deploy clean verify troubleshoot ci-local
.PHONY: migrate collectstatic runserver shell createsuperuser check showmigrations

## Quality gates (used by /flow:finish)

lint:
	uv run ruff check .

test:
	uv run python manage.py test --verbosity=2

## Recommended targets

typecheck:
	uv run mypy .

format:
	uv run ruff format .

build:
	uv build

## Pre-deploy gate (runs all quality checks)

verify: lint test typecheck check

## Django management commands

migrate:
	uv run python manage.py migrate

showmigrations:
	uv run python manage.py showmigrations

collectstatic:
	uv run python manage.py collectstatic --noinput

check:
	uv run python manage.py check --deploy

runserver:
	uv run python manage.py runserver

shell:
	uv run python manage.py shell

createsuperuser:
	uv run python manage.py createsuperuser

## Deployment (used by /flow:deploy)

deploy: verify migrate collectstatic
	@echo "TODO: Define your deploy steps here"
	@echo "Examples:"
	@echo "  ssh prod 'cd /app && git pull && uv sync && python manage.py migrate && systemctl restart gunicorn'"
	@echo "  docker compose up -d --build"

## Troubleshooting (single-command diagnostic pass)

troubleshoot: clean lint test check
	@echo "All checks passed — issue may be environmental"

## Local CI (requires: woodpecker-cli — https://woodpecker-ci.org/)

ci-local:
	woodpecker exec

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info .venv staticfiles
