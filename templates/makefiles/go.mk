# Makefile — Go (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# Requires: go, golangci-lint (https://golangci-lint.run/)
# Copy to your project root as "Makefile" and customize.

BINARY_NAME ?= $(shell basename $(CURDIR))
BUILD_DIR   ?= bin

.PHONY: lint test vet build clean verify troubleshoot tidy ci-local

## Quality gates (used by /flow:finish)

lint:
	golangci-lint run

test:
	go test ./...

## Recommended targets

vet:
	go vet ./...

build:
	go build -o $(BUILD_DIR)/$(BINARY_NAME) ./...

tidy:
	go mod tidy

## Pre-deploy gate (runs all quality checks)

verify: lint test vet

## Deployment (used by /flow:deploy)

# No deploy target is defined yet, on purpose (issue #1712): a target that
# only printed a TODO would report a successful deployment that deployed
# nothing. Uncomment the block below, replace its recipe with real steps, and
# add `deploy` to .PHONY (a .PHONY target with no rule makes `make deploy`
# exit 0 with "Nothing to be done").
#
# deploy: verify build
# 	<your deploy command>
# Examples:
#    scp $(BUILD_DIR)/$(BINARY_NAME) prod:/usr/local/bin/
#    docker build -t $(BINARY_NAME) . && docker push $(BINARY_NAME)

## Troubleshooting (single-command diagnostic pass)

troubleshoot: clean lint test vet
	@echo "All checks passed — issue may be environmental"

## Local CI (requires: woodpecker-cli — https://woodpecker-ci.org/)

ci-local:
	woodpecker exec

## Utilities

clean:
	rm -rf $(BUILD_DIR) coverage.out
	go clean -testcache
