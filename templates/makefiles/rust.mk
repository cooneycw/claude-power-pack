# Makefile — Rust (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# Requires: cargo, clippy, rustfmt
# Copy to your project root as "Makefile" and customize.

.PHONY: lint test format build build-release deploy clean verify

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

deploy: verify build-release
	@echo "TODO: Define your deploy steps here"
	@echo "Examples:"
	@echo "  scp target/release/$(shell basename $(CURDIR)) prod:/usr/local/bin/"
	@echo "  docker build -t $(shell basename $(CURDIR)) ."

## Utilities

clean:
	cargo clean
