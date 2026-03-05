# Makefile — Multi-language / Polyglot (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# Delegates to sub-project Makefiles. Adjust PROJECTS list and paths
# to match your monorepo structure.
# Copy to your project root as "Makefile" and customize.

# List sub-projects (directories containing their own Makefile)
PROJECTS := backend frontend

.PHONY: lint test build deploy clean verify troubleshoot ci-local $(PROJECTS)

## Quality gates (used by /flow:finish)
## Runs target in each sub-project that defines it

lint:
	@for proj in $(PROJECTS); do \
		if [ -f "$$proj/Makefile" ] && grep -q '^lint:' "$$proj/Makefile"; then \
			echo "=== lint: $$proj ==="; \
			$(MAKE) -C "$$proj" lint || exit 1; \
		fi; \
	done

test:
	@for proj in $(PROJECTS); do \
		if [ -f "$$proj/Makefile" ] && grep -q '^test:' "$$proj/Makefile"; then \
			echo "=== test: $$proj ==="; \
			$(MAKE) -C "$$proj" test || exit 1; \
		fi; \
	done

## Recommended targets

build:
	@for proj in $(PROJECTS); do \
		if [ -f "$$proj/Makefile" ] && grep -q '^build:' "$$proj/Makefile"; then \
			echo "=== build: $$proj ==="; \
			$(MAKE) -C "$$proj" build || exit 1; \
		fi; \
	done

## Pre-deploy gate (runs all quality checks)

verify: lint test

## Deployment (used by /flow:deploy)

deploy: verify build
	@echo "TODO: Define your deploy steps here"
	@echo "Examples:"
	@echo "  docker compose up -d --build"
	@echo "  $(MAKE) -C backend deploy && $(MAKE) -C frontend deploy"

## Troubleshooting (single-command diagnostic pass)

troubleshoot: clean lint test
	@echo "All checks passed — issue may be environmental"

## Local CI (requires: woodpecker-cli — https://woodpecker-ci.org/)

ci-local:
	woodpecker exec

## Utilities

clean:
	@for proj in $(PROJECTS); do \
		if [ -f "$$proj/Makefile" ] && grep -q '^clean:' "$$proj/Makefile"; then \
			$(MAKE) -C "$$proj" clean; \
		fi; \
	done
