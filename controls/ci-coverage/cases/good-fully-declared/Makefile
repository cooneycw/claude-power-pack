.PHONY: verify alpha-check beta-check

## verify-coverage: gate alpha-check - stdlib-only, so the pipeline runs it; ci: runs alpha-check
alpha-check:
	@python3 scripts/alpha-check.py

## verify-coverage: gate beta-check - reads git history, which the slim image has not got; ci: excluded needs-git
beta-check:
	@python3 scripts/beta-check.py

## Both sides of the clause are read here: `ci: runs <step>` is a claim, and
## a claim naming a step the pipeline has not got is not coverage. This
## sentence mentions the notation and must not read as a declaration.
## verify-coverage: gate verify - the aggregate itself
verify: alpha-check \
	beta-check
	@echo verified
