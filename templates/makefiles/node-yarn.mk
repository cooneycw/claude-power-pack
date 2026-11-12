# Makefile — Node.js + yarn (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  → runs `make lint` and `make test`
#   /flow:deploy  → runs `make deploy`
#   /flow:doctor  → reports which targets are available
#
# Assumes package.json scripts: "lint", "test", "build", "dev".
# Copy to your project root as "Makefile" and customize.

.PHONY: lint test typecheck build clean verify troubleshoot dev install ci-local

## Quality gates (used by /flow:finish)

lint:
	yarn lint

test:
	yarn test

## Recommended targets

typecheck:
	yarn tsc --noEmit

build:
	yarn build

dev:
	yarn dev

## Dependencies

install:
	yarn install --frozen-lockfile

## Pre-deploy gate (runs all quality checks)

verify: lint test typecheck

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
#    npx wrangler deploy          # Cloudflare
#    npx vercel --prod            # Vercel
#    aws s3 sync dist/ s3://bucket # S3 static

## Troubleshooting (single-command diagnostic pass)

troubleshoot: clean lint test
	@echo "All checks passed — issue may be environmental"

## Local CI (requires: woodpecker-cli — https://woodpecker-ci.org/)

ci-local:
	woodpecker exec

## Utilities

clean:
	rm -rf node_modules dist .next .nuxt .cache coverage
