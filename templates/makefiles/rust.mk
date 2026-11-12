# Makefile — Rust (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# Requires: cargo, clippy, rustfmt
# Copy to your project root as "Makefile" and customize.

.PHONY: lint test format build build-release clean verify troubleshoot ci-local

## Quality gates (used by /flow:finish)

lint:
	cargo clippy -- -D warnings

test:
	cargo test

## Recommended targets

format:
	cargo fmt

build:
	cargo build

build-release:
	cargo build --release

## Pre-deploy gate (runs all quality checks)

verify: lint test

## Deployment (used by /flow:deploy)

# No deploy target is defined yet, on purpose (issue #1712): a target that
# only printed a TODO would report a successful deployment that deployed
# nothing. Uncomment the block below, replace its recipe with real steps, and
# add `deploy` to .PHONY (a .PHONY target with no rule makes `make deploy`
# exit 0 with "Nothing to be done").
#
# deploy: verify build-release
# 	<your deploy command>
# Examples:
#    scp target/release/$(shell basename $(CURDIR)) prod:/usr/local/bin/
#    docker build -t $(shell basename $(CURDIR)) .

## Troubleshooting (single-command diagnostic pass)

troubleshoot: clean lint test
	@echo "All checks passed — issue may be environmental"

## Local CI (requires: woodpecker-cli — https://woodpecker-ci.org/)

ci-local:
	woodpecker exec

## Utilities

clean:
	cargo clean
