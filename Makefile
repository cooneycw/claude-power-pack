.PHONY: test lint format typecheck verify secret-scan update_docs clean \
       bootstrap-check drift-check deploy setup-woodpecker-cli \
       codex-init codex-skills codex-skills-check codex-install \
       eli5-check eli5-drift eli5-revendor \
       host-surfaces-check host-surfaces-plan host-surfaces-prune memory-harness

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

## Documentation (used by /flow:auto and /flow:finish)

update_docs:
	@echo "Run /documentation:c4 to regenerate C4 architecture diagrams"
	@echo "Review CLAUDE.md and README.md for accuracy"

## Bootstrap dependency check (admin-only prerequisites)

bootstrap-check:
	@scripts/bootstrap-check.sh

## Drift detection (compare host-installed artifacts against repo templates)

drift-check:
	@scripts/drift-detect.sh --fix

## Deploy (used by /flow:deploy and /flow:auto Step 9)
## CPP ships no deployable services as of #469 - the second-opinion MCP server
## runs from its own external repo (github.com/cooneycw/mcp-second-opinion) and
## CPP consumes it via .mcp.json. This target is an informative no-op so the
## flow deploy path stays intact without a container runtime.

deploy:
	@echo "Nothing to deploy: CPP no longer ships container services (issue #469)."
	@echo "The second-opinion MCP server runs from its own repo:"
	@echo "  https://github.com/cooneycw/mcp-second-opinion"
	@echo "Run that server, then point .mcp.json at it (localhost or Tailscale). See /cpp:init."

## Woodpecker CLI setup

setup-woodpecker-cli:
	@scripts/setup-woodpecker-cli.sh

## Codex skill generation (single-source -> per-harness, issue #555). The
## deprecated flat codex/prompts/ surface (issue #446) and its codex-prompts /
## codex-prompts-check targets were retired at the #556 cutover.

codex-skills-check:
	@python3 scripts/codex-skill-sync.py --check

codex-skills:
	@python3 scripts/codex-skill-sync.py --write

codex-init:
	@python3 scripts/codex-skill-sync.py --write --install

## Install the checked-in skills to ~/.codex/skills WITHOUT regenerating them -
## the host-refresh path used by /cpp:init Tier 5 and /cpp:update Step 7.9,
## where the repo copy is already current and CI-gated (issue #575). Prunes
## managed orphans at the destination; never touches unmarked or dotted entries.
codex-install:
	@python3 scripts/codex-skill-sync.py --install

## Vendored eli5-gate core (issue #591)
## The canonical home of the /flow:eli5 necessity gate is cooneycw/eli5-gate;
## CPP vendors its core between the eli5-core markers. Two complementary checks:
## eli5-check is OFFLINE and a hard gate (did the local core get edited out of
## band?); eli5-drift is a NETWORK, fail-open advisory (did upstream move?).
## Neither subsumes the other - a manifest cannot notice upstream moving.

eli5-check:
	@python3 scripts/eli5-vendor.py

eli5-drift:
	@python3 scripts/eli5-vendor.py --upstream

eli5-revendor:
	@python3 scripts/eli5-vendor.py --revendor

## Retired host surfaces (issue #575)
## Directories in HOME that CPP once generated into and no longer does. The
## generator gets deleted from the repo; the copies it already wrote stay put,
## unmaintained and silently loading. Curated by .claude/retired-surfaces.yaml,
## gated on the GENERATED marker, and reversible - prune MOVES files to a
## timestamped sibling rather than deleting them.

host-surfaces-check:
	@python3 scripts/retired-surface-prune.py --check

host-surfaces-plan:
	@python3 scripts/retired-surface-prune.py --plan

host-surfaces-prune:
	@python3 scripts/retired-surface-prune.py --prune --all

## Common-memory harness (issue #433): links scripts/cpp-memory onto PATH and
## installs the hand-authored Codex /cpp-memory prompt. Idempotent. Wired into
## /cpp:init Tier 5 and /cpp:update Step 7.9 (issue #575) - before that it was
## documented as re-runnable from /cpp:update but never actually invoked.
memory-harness:
	@bash scripts/install-memory-harness.sh

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
