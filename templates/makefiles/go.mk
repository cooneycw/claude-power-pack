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

.PHONY: lint test vet build deploy clean verify tidy

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

deploy: verify build
	@echo "TODO: Define your deploy steps here"
	@echo "Examples:"
	@echo "  scp $(BUILD_DIR)/$(BINARY_NAME) prod:/usr/local/bin/"
	@echo "  docker build -t $(BINARY_NAME) . && docker push $(BINARY_NAME)"

## Utilities

clean:
	rm -rf $(BUILD_DIR) coverage.out
	go clean -testcache
