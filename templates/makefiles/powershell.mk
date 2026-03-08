# Makefile - PowerShell (Claude Power Pack)
#
# CPP /flow integration:
#   /flow:finish  -> runs `make lint` and `make test`
#   /flow:deploy  -> runs `make deploy`
#   /flow:doctor  -> reports which targets are available
#
# Requires: pwsh (PowerShell 7+), Pester, PSScriptAnalyzer
# Install: pwsh -Command "Install-Module Pester, PSScriptAnalyzer -Force"
# Copy to your project root as "Makefile" and customize.

.PHONY: lint test format build deploy clean verify troubleshoot ci-local

## Quality gates (used by /flow:finish)

lint:
	pwsh -Command "Invoke-ScriptAnalyzer -Path . -Recurse -EnableExit"

test:
	pwsh -Command "Invoke-Pester -CI"

## Recommended targets

format:
	pwsh -Command "Invoke-ScriptAnalyzer -Path . -Recurse -Fix"

build:
	pwsh -Command "Build-Module"

## Pre-deploy gate (runs all quality checks)

verify: lint test

## Deployment (used by /flow:deploy)

deploy: verify build
	@echo "TODO: Define your deploy steps here"
	@echo "Examples:"
	@echo "  pwsh -Command 'Publish-Module -Path ./Output -NuGetApiKey \$$env:NUGET_API_KEY'"
	@echo "  pwsh -Command 'Publish-PSResource -Path ./Output'"

## Troubleshooting (single-command diagnostic pass)

troubleshoot: clean lint test
	@echo "All checks passed - issue may be environmental"

## Local CI (requires: woodpecker-cli - https://woodpecker-ci.org/)

ci-local:
	woodpecker exec

## Utilities

clean:
	rm -rf TestResults Output
