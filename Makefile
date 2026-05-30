.PHONY: test lint format typecheck verify secret-scan update_docs clean \
       docker-build docker-check-env docker-secrets-check docker-up docker-refresh docker-health docker-down docker-logs docker-ps deploy \
       bootstrap-check drift-check setup-woodpecker-cli second-opinion-model-smoke codex-init codex-init-workspace

## Quality gates (used by /flow:finish)

lint:
	uv run --extra dev ruff check .

format:
	uv run --extra dev ruff format .

test:
	uv run --extra dev pytest

typecheck:
	uv run --extra dev mypy .

secret-scan:
	@if command -v gitleaks > /dev/null 2>&1; then \
		gitleaks detect --source . --config .gitleaks.toml --no-git --verbose; \
	elif command -v docker > /dev/null 2>&1; then \
		docker run --rm -v "$$(pwd):/repo" zricethezav/gitleaks:latest detect --source /repo --config /repo/.gitleaks.toml --no-git --verbose; \
	else \
		echo "ERROR: gitleaks not found. Install via: brew install gitleaks / go install github.com/gitleaks/gitleaks/v8@latest"; \
		echo "       Or use Docker: docker run --rm -v \$$(pwd):/repo zricethezav/gitleaks:latest detect --source /repo"; \
		exit 1; \
	fi

## Pre-deploy gate (runs all quality checks)

verify: lint test typecheck

second-opinion-model-smoke:
	env UV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} uv run --directory mcp-second-opinion python scripts/smoke-model-catalog.py

## Documentation (used by /flow:auto and /flow:finish)

update_docs:
	@echo "Run /documentation:c4 to regenerate C4 architecture diagrams"
	@echo "Review CLAUDE.md and README.md for accuracy"

## Docker (MCP server containers)
## Usage: make docker-up PROFILE=core
##        make docker-up PROFILE="core browser"
##        make docker-refresh PROFILE="core browser cicd"
## Profiles: core (second-opinion + nano-banana), browser, cicd

PROFILE ?= core
DOCKER_UP_FLAGS ?= -d
DOCKER_PROFILES = $(foreach p,$(PROFILE),--profile $(p))

docker-build:
	docker compose $(DOCKER_PROFILES) build

docker-check-env:
	@python3 scripts/check-docker-aws-env.py --profiles "$(PROFILE)"

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
	python3 scripts/check-aws-secret-keys.py \
		--required codex_llm_apikeys:GEMINI_API_KEY,OPENAI_API_KEY,ANTHROPIC_API_KEY,MISTRAL_API_KEY,GROQ_API_KEY,OPENROUTER_API_KEY,DEEPSEEK_API_KEY \
		--optional essent-ai:WOODPECKER_URL,WOODPECKER_API_TOKEN
	@echo "Done."

docker-up: docker-check-env
	docker compose $(DOCKER_PROFILES) up $(DOCKER_UP_FLAGS)

docker-refresh:
	@$(MAKE) docker-up PROFILE="$(PROFILE)" DOCKER_UP_FLAGS="-d --build --wait"
	@$(MAKE) docker-health PROFILE="$(PROFILE)"

docker-health:
	docker compose $(DOCKER_PROFILES) ps
	@python3 scripts/docker-health-check.py --profiles "$(PROFILE)"

docker-down:
	docker compose --profile core --profile browser --profile cicd down

docker-logs:
	docker compose --profile core --profile browser --profile cicd logs -f

docker-ps:
	docker compose --profile core --profile browser --profile cicd ps

## Bootstrap dependency check (admin-only prerequisites)

bootstrap-check:
	@scripts/bootstrap-check.sh

## Drift detection (compare host-installed artifacts against repo templates)

drift-check:
	@scripts/drift-detect.sh --fix

## Deploy (used by Woodpecker CI and /flow:deploy)

deploy: docker-refresh

## Woodpecker CLI setup

setup-woodpecker-cli:
	@scripts/setup-woodpecker-cli.sh

## Codex skill wrapper generation

codex-init:
	@python3 scripts/codex-skill-gen.py

codex-init-force:
	@python3 scripts/codex-skill-gen.py --force

codex-init-workspace:
	@python3 scripts/codex-skill-gen.py --force --workspace-root ..

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
