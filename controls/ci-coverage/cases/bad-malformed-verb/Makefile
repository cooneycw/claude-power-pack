.PHONY: verify alpha-check beta-check

## verify-coverage: gate alpha-check - stdlib-only, so the pipeline runs it; ci: run alpha-check
alpha-check:
	@python3 scripts/alpha-check.py

## verify-coverage: gate beta-check - reads git history, which the slim image has not got; ci: excluded needs-git
beta-check:
	@python3 scripts/beta-check.py

## verify-coverage: gate verify - the aggregate itself
verify: alpha-check \
	beta-check
	@echo verified
