# Makefile — Node.js + npm (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# Assumes package.json scripts: "lint", "test", "build", "dev".
# Copy to your project root as "Makefile" and customize.

.PHONY: lint test typecheck build deploy clean verify dev install ci-local

## Quality gates (used by /flow:finish)

lint:
	npm run lint

test:
	npm test

## Recommended targets

typecheck:
	npx tsc --noEmit

build:
	npm run build

dev:
	npm run dev

## Dependencies

install:
	npm ci

## Pre-deploy gate (runs all quality checks)

verify: lint test typecheck

## Deployment (used by /flow:deploy)

deploy: verify build
	@echo "TODO: Define your deploy steps here"
	@echo "Examples:"
	@echo "  npx wrangler deploy          # Cloudflare"
	@echo "  npx vercel --prod            # Vercel"
	@echo "  aws s3 sync dist/ s3://bucket # S3 static"

## Local CI (requires: woodpecker-cli — https://woodpecker-ci.org/)

ci-local:
	woodpecker exec

## Utilities

clean:
	rm -rf node_modules dist .next .nuxt .cache coverage
