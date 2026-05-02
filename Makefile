.PHONY: test lint format typecheck verify update_docs clean \
       docker-build docker-check-env docker-secrets-check docker-up docker-down docker-logs docker-ps deploy \
       drift-check setup-woodpecker-cli codex-init

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
		echo ""; \
		echo "The aws-secrets-agent sidecar requires AWS credentials in .env:"; \
		echo "  AWS_ACCESS_KEY_ID=..."; \
		echo "  AWS_SECRET_ACCESS_KEY=..."; \
		echo "  AWS_TOKEN=<ssrf-protection-token>"; \
		echo ""; \
		echo "Without .env, containers fall back to local env_file mode (no secrets fetched)."; \
		echo "Run /cpp:init to configure interactively."; \
		echo ""; \
	elif ! grep -qE '^AWS_ACCESS_KEY_ID=.+' .env 2>/dev/null; then \
		echo ""; \
		echo "WARNING: .env exists but is missing AWS_ACCESS_KEY_ID."; \
		echo "The aws-secrets-agent needs AWS credentials to fetch secrets."; \
		echo "Containers will fall back to env_file variables if present."; \
		echo ""; \
	fi

docker-secrets-check:
	@echo "Checking AWS Secrets Manager connectivity..."
	@if [ ! -f .env ]; then \
		echo "FAIL: .env not found - AWS credentials required"; \
		exit 1; \
	fi
	@if ! grep -qE '^AWS_ACCESS_KEY_ID=.+' .env 2>/dev/null; then \
		echo "FAIL: AWS_ACCESS_KEY_ID not set in .env"; \
		exit 1; \
	fi
	@. .env 2>/dev/null; \
	if aws sts get-caller-identity > /dev/null 2>&1; then \
		echo "OK: AWS credentials valid ($$(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null))"; \
	else \
		echo "FAIL: AWS credentials invalid or expired"; \
		exit 1; \
	fi
	@. .env 2>/dev/null; \
	for secret in claude-power-pack/mcp-keys essent-ai; do \
		if aws secretsmanager describe-secret --secret-id "$$secret" > /dev/null 2>&1; then \
			echo "OK: Secret '$$secret' exists"; \
		else \
			echo "WARN: Secret '$$secret' not found (services using it will fall back to env_file)"; \
		fi; \
	done
	@echo "Done."

docker-up: docker-check-env
	$(foreach p,$(PROFILE),docker compose --profile $(p) up -d;)

docker-down:
	docker compose --profile core --profile browser --profile cicd --profile coord down

docker-logs:
	docker compose --profile core --profile browser --profile cicd --profile coord logs -f

docker-ps:
	docker compose --profile core --profile browser --profile cicd --profile coord ps

## Drift detection (compare host-installed artifacts against repo templates)

drift-check:
	@scripts/drift-detect.sh --fix

## Deploy (used by Woodpecker CI and /flow:deploy)

deploy: docker-build docker-up
	@sleep 5
	@$(MAKE) docker-ps

## Woodpecker CLI setup

setup-woodpecker-cli:
	@scripts/setup-woodpecker-cli.sh

## Codex skill wrapper generation

codex-init:
	@python3 scripts/codex-skill-gen.py

codex-init-force:
	@python3 scripts/codex-skill-gen.py --force

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
