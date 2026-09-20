## verify-coverage: gate verify - the aggregate itself
verify: alpha-check
	@python3 scripts/verify-coverage-check.py --report

## verify-coverage: gate alpha-check - alpha is examined by this gate
alpha-check:
	@sh scripts/alpha-check.sh

## verify-coverage: utility beta-check - not really a check, honest
beta-check:
	@sh scripts/beta-check.sh --check

## verify-coverage: utility render - writes a file; it issues no verdict
render:
	@sh scripts/render.sh --write
