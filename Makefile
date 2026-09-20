.PHONY: test lint format typecheck verify shellcheck secret-scan tools-check \
	scripts-inventory-check instrument-census-check dep-audit dep-audit-selftest dep-audit-capture \
	bandit-audit bandit-audit-selftest bandit-audit-capture \
	undeclared-import-audit undeclared-import-audit-selftest \
       oscillation update_docs clean \
       bootstrap-check drift-check deploy setup-woodpecker-cli \
       codex-init codex-skills codex-skills-check codex-install \
       eli5-check eli5-drift eli5-revendor \
       project-next-check project-next-repin \
       host-surface-check host-surface-manifest \
       cpp-host-writes-check \
       tool-risk-check tool-risk-drift \
       branch-protection-check branch-protection-apply branch-protection-show \
       host-surfaces-check host-surfaces-plan host-surfaces-prune memory-harness \
       binary-guards-check negative-fixture-check negative-controls claude-md-budget-check \
       agents-md-budget-check \
       claude-md-links-check claude-md-behavior-check skills-check \
       install-drift-check install-drift-list \
       tools-version-check toolchain-provenance checkout-readers \
       delegated-core-check delegated-core-write \
       version-consistency-check unicode-dashes-check co-authored-by-trailer-check

## `make` with no target ran `lint` because lint was the first target. Adding
## tools-check above it silently made THAT the default - bare `make` would print
## a diagnostic and succeed without linting anything. Declared explicitly so the
## default stops depending on file order (issue #987 review).
.DEFAULT_GOAL := lint

## DECLARE WHAT `verify` NEEDS, AND NAME EVERYTHING ABSENT (issue #987).
##
## Two undeclared hard dependencies landed in one day - shellcheck at 07:00
## (#960) and gitleaks at 19:00 (#935, reached through `make test` ->
## test_negative_controls -> controls/secret-scan). Neither was declared
## anywhere: not README Requirements, not /cpp:init, not .pre-commit-config.
## A clean clone could not pass the repository's own documented gate, while CI
## stayed green because the pipeline images supply the tools.
##
## The failure mode this target removes is not "a tool is missing" - make
## already said that. It is that make says it about the FIRST missing tool and
## stops, so a developer installs one, re-runs five minutes of gate, and meets
## the next one. This reports the whole set in one pass, with what each is for,
## and never fails on a tool that has a working fallback.
##
## It does not gate: absence is reported and `verify` continues to the target
## that actually needs the tool, which is where the honest verdict lives (the
## shellcheck gate's own `unknown`, exit 2). Naming a missing tool early is
## diagnosis; deciding what it means belongs to the instrument.
## TWO CLASSES, because docker does not substitute equally (issue #987 review).
## `make shellcheck` and `make secret-scan` fall back to a pinned image, so
## docker covers them. `make test` does NOT: it runs registered controls that
## invoke scripts/shellcheck-gate.sh and scripts/secret-scan-check.sh directly,
## and those need the scanner on PATH. Reporting "available via docker" for the
## test path would be the overclaim this target exists to remove.
TOOLS_HARD := git python3 uv
TOOLS_NATIVE := shellcheck gitleaks jq

## verify-coverage: gate tools-check - reports every external tool verify needs, before the target that needs it
tools-check:
	@missing=""; \
	for t in $(TOOLS_HARD); do \
		command -v $$t > /dev/null 2>&1 || missing="$$missing\n  $$t - required, no fallback"; \
	done; \
	native=""; \
	for t in $(TOOLS_NATIVE); do \
		command -v $$t > /dev/null 2>&1 || native="$$native $$t"; \
	done; \
	if [ -n "$$missing" ]; then \
		printf 'tools-check: NOT on PATH and with no fallback:%b\n' "$$missing"; \
	fi; \
	if [ -n "$$native" ]; then \
		printf 'tools-check: NOT on PATH:%s\n' "$$native"; \
		if command -v docker > /dev/null 2>&1; then \
			printf '  docker is present, so `make shellcheck` and `make secret-scan` still run, pinned:\n'; \
			printf '    %s\n    %s\n' '$(SHELLCHECK_IMAGE)' '$(GITLEAKS_IMAGE)'; \
			printf '  but `make test` and `make negative-controls` run controls that invoke these scanners DIRECTLY, with no such fallback,\n'; \
			printf '  so controls/shellcheck-gate and controls/secret-scan report UNAVAILABLE there (#1117): unexamined, not clean.\n'; \
		else \
			printf '  docker is absent too, so the shellcheck and secret-scan targets cannot run either.\n'; \
		fi; \
	fi; \
	if [ -z "$$missing" ] && [ -z "$$native" ]; then \
		printf 'tools-check: ok - every external tool verify needs is on PATH.\n'; \
	else \
		printf 'tools-check: verify continues; each target reports its own verdict.\n'; \
	fi; \
	scripts/tools-version-check.sh --quiet || true

## PRESENT IS NOT CURRENT (issue #1029). `tools-check` above asks `command -v`,
## which any version satisfies identically - so a host whose apt supplied
## shellcheck 0.9.0 gets `tools-check: ok` and a controls/shellcheck-gate verdict
## that need not match CI's, which is the exact thing .woodpecker.yml pins the
## image to prevent ("running the gate under two different linters would make the
## control's verdict depend on which container reached it", its own words).
## The pinned version is PARSED from the declarations that already exist
## (SHELLCHECK_IMAGE, GITLEAKS_IMAGE, ci-stage-jq.py's JQ_URL) - never re-typed
## here, which would be a third copy to go stale. Advisory, like tools-check:
## it reports and never gates.
## verify-coverage: excluded tools-version-check - advisory version parity; the `--quiet` form already runs inside tools-check
tools-version-check:
	@scripts/tools-version-check.sh

## WHAT VERSION IS THE EXECUTED COPY? (issue #1029). Every install-parity check
## compares against THE CHECKOUT and none of them can say how current that is;
## on 2026-09-15 it was 21 commits behind main while every session ran from it.
## verify-coverage: excluded toolchain-provenance - reports how current THIS checkout is - a fact about the host, not the tree
toolchain-provenance:
	@scripts/toolchain-provenance.sh

## WHO IS HOLDING THE CHECKOUT RIGHT NOW? (issue #1029). Names the pids running
## DELETED files from this tree (a pull did not reach them) and the pids holding
## current ones (a pull now hot-swaps instruments under a running gate). `clear`
## is the declared safe moment for the pull.
## verify-coverage: excluded checkout-readers - names the pids holding this checkout - a fact about the host, not the tree
checkout-readers:
	@scripts/checkout-readers.sh

## Quality gates (used by /flow:finish)

## verify-coverage: gate lint - ruff over the tree
lint:
	uv run --extra dev ruff check .

## verify-coverage: utility format - ruff format writes the tree; it issues no verdict
format:
	uv run --extra dev ruff format .

## PARALLEL, WITH AN EXPLICIT CAP - never `-n auto` (issues #640, #1086).
##
## 4,342 tests ran one after another here, at 83% of ONE core on a 24-core box,
## with system time EXCEEDING user time (186.7s user, 227.0s sys) - the signature
## of a suite that WAITS rather than one that computes; 70 of 119 test modules
## import `subprocess`.
##
## Measured on this tree, four full runs: serial 496.5s, `-n 8` 83.3s (5.96x),
## `-n 4` 123.0s (4.04x). Total CPU moved by under 6% across all of them
## (413.7s / 413.3s / 405.1s user+sys), which is what says the wall time was wait
## and not work - the same work, spent waiting in one process or in eight.
##
## The numbers are a FLOOR, not a flattering figure: they were taken on a loaded
## fleet host (load 8-22), and contention penalises the parallel arm harder than
## the serial one.
##
## `scripts/pytest-workers.sh` owns the number and the refusal, so `make test`
## and the CI `validate` step resolve it identically instead of each naming one.
## It prints `pytest-workers: -n N (source: ...)` to stderr, which is what makes
## the cap visible in this target's output rather than inferable from the file.
##
## THE `$$(...)` IS NOT COSMETIC: a resolver that REFUSES (exit 2) must not leave
## `-n` holding an empty string, because `pytest -n ''` is an argument error whose
## message is about pytest usage rather than about the cap that was rejected. `set
## -e` inside the recipe's single shell makes the refusal the failure that stops
## the target, with the resolver's own diagnosis already on stderr.
## verify-coverage: gate test - the pytest suite, which is also where several checkers' real-repo pins live
test:
	@set -e; workers="$$(sh scripts/pytest-workers.sh)"; \
		uv run --extra dev pytest -n "$$workers"

## verify-coverage: gate typecheck - mypy over the tree
typecheck:
	uv run --extra dev mypy .

## Lint every shell script in the tree (issue #960). Membership is DERIVED,
## not globbed: `git ls-files '*.sh'` cannot see `scripts/cpp-memory`, a tracked
## bash script with no .sh suffix, and a tracked-only list cannot see untracked
## scripts at all. The helper reports the denominator it examined on every run.
##
## Absence of shellcheck is UNKNOWN and exits non-zero. It is NOT a pass: a
## `command -v shellcheck || exit 0` guard would go green on every machine that
## lacks the tool, which is the failure class this repo keeps finding.
## THE SAME DIGEST .woodpecker.yml PINS (issue #987). `secret-scan` below has
## carried this shape since #935; `shellcheck` did not, so a clean clone hit a
## hard undeclared dependency at verify's fourth target. A docker fallback is
## strictly better than an install instruction here: apt supplies 0.9.0 and CI
## pins 0.10.0, and .woodpecker.yml already records why that matters - "running
## the gate under two different linters would make the control's verdict depend
## on which container reached it". An install instruction would reintroduce the
## exact skew #960 designed around; this gets version parity for free.
##
## The gate's own `command -v shellcheck || unknown` (exit 2) is NOT touched.
## Absence must stay UNKNOWN rather than become a pass - the fix is to SUPPLY
## the tool, never to soften the gate.
SHELLCHECK_IMAGE := koalaman/shellcheck-alpine:v0.10.0@sha256:5921d946dac740cbeec2fb1c898747b6105e585130cc7f0602eec9a10f7ddb63

## verify-coverage: gate shellcheck - every shell script in the tree, with a pinned docker fallback
shellcheck:
	@if command -v shellcheck > /dev/null 2>&1; then \
		sh scripts/shellcheck-gate.sh; \
	elif command -v docker > /dev/null 2>&1; then \
		docker run --rm -v "$$(pwd):/repo" -w /repo \
			-e SHELLCHECK_SEVERITY="$${SHELLCHECK_SEVERITY:-error}" \
			--entrypoint sh $(SHELLCHECK_IMAGE) scripts/shellcheck-gate.sh; \
	else \
		sh scripts/shellcheck-gate.sh; \
	fi

## The SAME digest .woodpecker.yml pins. Three paths could reach this gate - CI's
## pinned image, a `gitleaks` on PATH, and this docker fallback - and two of them
## were unpinned. A control proving "gitleaks detects this shape" is meaningless
## without saying WHICH gitleaks, and detection here is measurably ruleset- and
## length-sensitive, so a tag that moves changes the verdict with no commit
## anywhere. `.woodpecker.yml` already carries this reasoning for shellcheck:
## "running the gate under two different linters would make the control's verdict
## depend on which container reached it." It applies here and nobody had applied it.
##
## `:latest` resolved to v8.30.1 on 2026-09-15 - the same version CI pins - which
## is exactly why the divergence went unnoticed. An instrument that is
## accidentally correct today is the hardest kind to retire.
GITLEAKS_IMAGE := zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f

## verify-coverage: excluded secret-scan - needs gitleaks on PATH or docker; CI runs it as its own step, over git HISTORY rather than the working tree
secret-scan:
	@if command -v gitleaks > /dev/null 2>&1; then \
		gitleaks detect --source . --config .gitleaks.toml --no-git --verbose; \
	elif command -v docker > /dev/null 2>&1; then \
		docker run --rm -v "$$(pwd):/repo" $(GITLEAKS_IMAGE) detect --source /repo --config /repo/.gitleaks.toml --no-git --verbose; \
	else \
		echo "ERROR: gitleaks not found. Install via: brew install gitleaks / go install github.com/gitleaks/gitleaks/v8@latest"; \
		echo "       Or use Docker: docker run --rm -v \$$(pwd):/repo zricethezav/gitleaks:latest detect --source /repo"; \
		exit 1; \
	fi

## Dependency vulnerability audit (issue #961)
## CPP ran no dependency audit at all. Both sets of advisories it carried were
## found by a person looking - #922 on the root lock ("tracked by no issue"),
## #943 on mcp-evaluate - which is a practice, not a gate. Advisories arrive
## whether or not anything is watching. Both are resolved now (#922 by upgrading,
## #943 by retiring the subproject), so the ledger is empty - which is a reading
## this gate takes, not a reason to stop taking it.
##
## DELIBERATELY NOT IN `verify`, and this is the mirror image of `oscillation`
## above rather than an oversight. That detector is in `verify` and NOT in CI
## because it needs git and the CI image has none. This one is in CI and NOT in
## `verify` because it needs the NETWORK: `verify` is the gate a developer runs
## on a plane, and a target that turns UNKNOWN without connectivity would make
## the whole aggregate unrunnable offline. Its verdict is consumed by the CI
## `dependency-audit` step, which is where it gates.
##
## REVERSAL TRIGGER (ADR 0009, pre-committed): this holds only while `verify` is
## an offline-capable local gate. If `verify` ever acquires another target that
## REQUIRES the network, the reason for this exclusion is gone and `dep-audit`
## should join it. Check with `grep -c 'curl\|--upstream' Makefile` inside the
## `verify` prerequisite list, which names nothing today.
##
## The posture is decided, not defaulted (issue #961 asks for it explicitly):
## a finding exits 1, a stale suppression exits 1, and UNKNOWN - pip-audit
## absent, `uv` absent, the feed unreachable, or a zero-file population - exits
## 2 with `DEP-AUDIT-UNKNOWN:`. Unknown is never a pass, the same rule the
## shellcheck gate holds for a missing binary, and the two outcomes never print
## the same sentence. `pip-audit` is NOT added to TOOLS_NATIVE above: that list
## drives a message about controls in `make test` reporting UNSIGNALLED without
## the tool, and this gate's control replays committed captures offline, so it
## needs neither pip-audit nor the network. Saying otherwise there would be an
## overclaim in the one target that exists to state dependencies honestly.

## verify-coverage: excluded dep-audit - needs the network and the OSV feed; verify is the gate a developer runs on a plane (see this target's own REVERSAL TRIGGER)
dep-audit: dep-audit-selftest
	@python3 scripts/dependency-audit.py

## The LIVE positive control, run BEFORE the audit above on purpose. A scan that
## cannot see prints the same clean line as a clean tree, so this audits two
## committed fixtures first - a 2019 PyYAML pin that must report, a clean pin
## that must not - and the real verdict is only issued afterwards.
## verify-coverage: excluded dep-audit-selftest - the live positive control for dep-audit, carrying the same network dependency
dep-audit-selftest:
	@python3 scripts/dependency-audit.py --selftest

## Record this tree's raw pip-audit reports, for building or refreshing the
## offline control fixtures under controls/dependency-audit/cases/.
## verify-coverage: utility dep-audit-capture - records raw pip-audit reports for building the offline control fixtures; it issues no verdict
dep-audit-capture:
	@python3 scripts/dependency-audit.py --capture dependency-audit-capture.json

## Python static security analysis (issue #962)
## CPP ran no Python SAST at all, across 113 tracked files under lib/ and
## scripts/ - while lib/security/ is this repository's own secret scanner and
## lib/creds/ handles credential retrieval. A repository shipping security
## tooling that runs no static analysis over that tooling is the gap.
##
## THE INHERITED SKIP LIST IS NOT COPIED, and that is the whole of #962.
## codex-power-pack runs `bandit -r lib scripts -ll --quiet --skip
## B104,B108,B310,B602`; measured on this tree, that list removes 10 of 11
## MEDIUM+ findings, because B602 (shell=True) and B108 (hard-coded /tmp) are
## exactly what a repository of shell-out helpers and deploy locks does. The
## skip list here is EMPTY and the residual lives one line per (file, rule) in
## `.bandit-audit-allow`, counted, printed on every run, and red when a line
## outlives the finding it records. The gate additionally REFUSES a --skip
## arriving by any route and REFUSES an inline `# nosec`, so the decision is
## mechanical rather than remembered.
##
## IN `verify`, unlike `dep-audit` - and the asymmetry is the reason, not an
## inconsistency. `dep-audit` is excluded because it REQUIRES THE NETWORK and
## verify is the gate a developer runs on a plane. bandit is a local analyser
## pinned in the dev extra, so after `uv sync` this needs nothing but the
## checkout, and dep-audit's pre-committed reversal trigger ("if verify ever
## acquires another target that REQUIRES the network") is deliberately NOT
## fired by this target.
##
## Run through `uv run --extra dev` rather than a bare `python3`, so the bandit
## that runs is the one uv.lock pins. A linter's ruleset moves between releases
## and .woodpecker.yml already records what that costs for shellcheck: "running
## the gate under two different linters would make the control's verdict depend
## on which container reached it."

## verify-coverage: gate bandit-audit - static security analysis; bandit is pinned in the dev extra, so this needs nothing but the checkout
bandit-audit: bandit-audit-selftest
	@uv run --extra dev python scripts/bandit-audit.py

## The LIVE positive control, run BEFORE the audit above on purpose. A scan that
## cannot see prints the same clean line as a clean tree, so this scans two
## committed fixture trees first - a B307 `eval` that must report, a clean tree
## that must not - and the real verdict is only issued afterwards. Its offline
## sibling, controls/bandit-audit, proves the ADJUDICATION discriminates; this
## proves bandit was invoked at all, and against the files we meant. Neither is
## sufficient alone.
## verify-coverage: gate bandit-audit-selftest - the live positive control bandit-audit runs first, so this gate reaches it too
bandit-audit-selftest:
	@uv run --extra dev python scripts/bandit-audit.py --selftest

## Record this tree's raw bandit report, for building or refreshing the offline
## control fixtures under controls/bandit-audit/cases/.
## verify-coverage: utility bandit-audit-capture - records a raw bandit report for building the offline control fixtures; it issues no verdict
bandit-audit-capture:
	@uv run --extra dev python scripts/bandit-audit.py --capture bandit-audit-capture.json

## Undeclared-import gate (issue #1041)
## `dep-audit` asks OSV about what `uv.lock` PINS, so a package imported directly
## and declared nowhere is never queried and cannot appear in any advisory row
## however vulnerable it is. Three files did exactly that, since the initial
## commit; `[tool.mypy] ignore_missing_imports = true` and ruff's E/F/W/I could
## none of them see it.
##
## IN `verify`, and the reason is the mirror of `dep-audit`'s exclusion one target
## up. This gate reads COMMITTED METADATA ONLY - `pyproject.toml` and the tree -
## never the network and never the ambient environment, which #1044 closed one
## gate over. Stdlib-only (`ast` + `tomllib`), so a bare `python3` gives the same
## verdict on the plane, in `verify`, and in the slim CI image.
##
## HARD, with no `failure: ignore`: an undeclared module-level import exits 1, a
## ledger line that accounts for nothing exits 1, and UNKNOWN - no pyproject, a
## file that will not parse, an unreadable ledger, a zero-file population - exits
## 2. Unknown is not a pass, and "no finding" and "could not look" never print the
## same sentence.
## verify-coverage: gate undeclared-import-audit - refuses an import no dependency metadata declares; stdlib-only and offline, so it needs nothing but the checkout
undeclared-import-audit: undeclared-import-audit-selftest
	@python3 scripts/undeclared-import-audit.py

## The LIVE positive control, run BEFORE the audit above on purpose. A scan that
## cannot see prints the same clean line as a clean tree, so the real code path is
## pointed at two committed trees first - one holding a planted module-level
## `import requests` it must report, one clean it must not - and the real verdict
## is only issued afterwards. Its offline sibling, controls/undeclared-import-audit,
## proves the ADJUDICATION discriminates; this proves the scan ran at all, over the
## files we meant. Neither is sufficient alone.
## verify-coverage: gate undeclared-import-audit-selftest - the live positive control undeclared-import-audit runs first, so this gate reaches it too
undeclared-import-audit-selftest:
	@python3 scripts/undeclared-import-audit.py --selftest

## Pre-deploy gate (runs all quality checks)

## Report knobs that have been moved BACK (issue #936, ADR 0009). It REPORTS:
## `found` and `none` both exit 0, and only `unknown` - this run could not look -
## is non-zero. A blocking detector that flags every threshold edit gets switched
## off, and switching it off is itself an oscillation.
##
## REVERSAL TRIGGER 1 (issue #936): `--exit-on-finding` must NEVER appear in a
## build target. That flag exists solely so controls/check-oscillation can
## register a two-sided case, because the control framework decides a case from
## the exit code. If it ever appears below, the detector has become blocking,
## which the owner ruled against. tests/test_oscillation_control.py asserts the
## build does not use it.
##
## REVERSAL TRIGGER 2 (issue #987, pre-committed): this target is in `verify` and
## NOT in CI because the detector needs git and the CI image has none - verify is
## a LOCAL gate and .woodpecker.yml runs no make targets at all. Check with
## `grep -c 'make verify' .woodpecker.yml`, which is 0 today. IF THAT EVER
## BECOMES NON-ZERO, this target's git dependency becomes a CI failure, and it
## then needs a git-bearing image or it comes out of verify.
##
## Absent from CI ON PURPOSE, not forgotten: the CONTROL runs there instead.
## controls/check-oscillation feeds the gate committed `git log` captures
## (`--from-log`), which need no git, so CI proves the detector CAN discriminate
## while these local runs prove it IS used. Neither alone is enough.
## verify-coverage: gate oscillation - reports knobs moved back; needs git, which is why it is here and not in CI
oscillation:
	@python3 scripts/check-oscillation.py

## verify-coverage: gate verify - the aggregate itself - its own failure mode is a sub-gate dropped from this list, which is what verify-coverage-check exists to catch
verify: tools-check lint test typecheck shellcheck bandit-audit undeclared-import-audit oscillation \
	binary-guards-check negative-fixture-check negative-controls \
	claude-md-budget-check agents-md-budget-check claude-md-links-check claude-md-behavior-check \
	project-next-check delegated-core-check codex-skills-check \
	scripts-inventory-check instrument-census-check verify-coverage-check \
	control-ci-deps-check \
	consolidation-ledger-check host-surface-check cpp-host-writes-check \
	version-consistency-check unicode-dashes-check co-authored-by-trailer-check
	@python3 scripts/verify-coverage-check.py --report

## ACCOUNT FOR EVERY CHECKER, AND SAY WHAT THIS GATE SKIPPED (issue #1028)
##
## Four checkers were found at once with no path from a change to a verdict
## anyone consumes, and the common remedy is not four wirings - it is answering,
## mechanically, the question a green from `verify` silently begs: what did it
## NOT run? The prerequisite above makes the accounting a hard gate; the RECIPE
## above prints the closing report, and it is a recipe rather than another
## prerequisite so it runs after every member has, even under `-j`.
##
## RUNNING IT TWICE IS DELIBERATE. As a prerequisite it fails early, on its own
## line, beside the other gates. As the recipe it prints a summary - and a
## summary is only worth the enumeration behind it, so the reporting run
## re-checks rather than trusting that an earlier one did. The script is
## stdlib-only and offline; the second run costs milliseconds.
##
## THE POPULATION THAT CATCHES A NEW CHECKER IS `scripts/`, NOT THIS FILE. A
## framework that classified only Makefile targets would be satisfied by a
## checker that never gets one, and 56 of this repository's 90 scripts have no
## target. `check-negative-controls.py` was one of them until the target below
## was added - one of #1028's own four subjects, invocable only by remembering a
## script path and its `--strict`, which is exactly how a checker goes unnoticed.
## Scripts no build surface invokes are accounted for in
## `.claude/verify-coverage.json`, and a new file in `scripts/` reddens this
## gate until it has an entry there or a target here.
##
## controls/verify-coverage registers the committed BAD/GOOD trees, since a gate
## that lets work through cannot be trusted on a clean tree alone - and this one
## least of all: a report that under-names is indistinguishable from a
## repository with less to name.

## verify-coverage: gate verify-coverage-check - every Makefile target is classified against this list, and every file in scripts/ is accounted for
verify-coverage-check:
	@python3 scripts/verify-coverage-check.py

## Would a registered control RUN in the image that runs the battery? (issue #1036)
##
## A control registered committed bare git repositories as its cases; `git` is not
## in the `negative-controls` image, and because the harness REFUSES to skip a
## control it cannot run, that one control made the gate that reports on every
## other control unable to report. It passed `make verify`, `--strict`, sixteen
## killed mutations and two review passes locally first - the dev box has git, so
## the condition is structurally invisible here unless something asks the question
## deliberately.
##
## IT ASKS A QUESTION THE BATTERY CANNOT ASK OF ITSELF, and that is why it is a
## separate target rather than folded in. #1036 wrote "in `verify` precisely
## because the battery is NOT", which was true for one day: #1117 put the battery
## in `verify` too, so the reason has changed even though the target has not. What
## it does that running the battery cannot is answer the question for the CI
## IMAGE rather than for this host - it READS the pipeline and the manifests and
## runs nothing, so it needs no binary the battery needs and gives the same
## verdict on a dev box as in the image it is asking about. A green battery here
## still says nothing about whether those controls can run there.
## verify-coverage: gate control-ci-deps-check - every registered control's examined surface resolves against the binaries the battery's CI step provides
control-ci-deps-check:
	@python3 scripts/check-control-ci-deps.py

## THE CONTROL BATTERY, NOW CONSUMED BY `verify` (issue #1117, closing #1028's
## other half). #1028 gave this a target and had `verify` NAME it as unexamined,
## with the reason; this is the half that makes the reason go away.
##
## WHAT `make verify` ALREADY PAID FOR AND DID NOT READ: `make test` runs the
## whole battery twice, through `tests/test_negative_controls.py:567` and `:876`.
## Neither passes `--strict` and neither asserts a battery-wide verdict - one
## reads a single control's block, the other the universe line - so 21 of 22
## verdicts were computed and discarded on every local run. A control that
## stopped discriminating on a dev box was silent here and reddened only in CI.
##
## WHY IT COULD NOT SIMPLY BE ADDED. `controls/secret-scan` needs gitleaks,
## `controls/shellcheck-gate` needs shellcheck and
## `controls/flow-driver-retirement-check` needs jq, and the harness REFUSES to
## skip a control it cannot run - correctly. But it filed that refusal as a fault
## in OUR CODE: UNSIGNALLED for the first two and, MEASURED, BLIND for the jq one,
## whose unavailability line is a legitimate member of its own detection pattern.
## So a host missing any of the three would have failed `verify` for an
## environment reason. #1117 split UNAVAILABLE out as its own verdict, which is
## what makes this target consumable here.
##
## `--allow-unavailable` IS THE LOCAL POSTURE AND NOT THE CI ONE. CI keeps bare
## `--strict` (.woodpecker.yml `negative-controls`), where an absent binary means
## a staging step stopped delivering and is still a red - both that file and
## tests/test_shellcheck_stage.py rest on exactly that.
##
## WHAT IT TOLERATES IT ALSO SAYS: the run names every unexamined control and
## drops it from the "N discriminate" numerator, so a green here on a tool-less
## box cannot be read as the evidence CI has. `tools-check` above names the
## missing binaries at the top of the same verify run.
##
## controls/check-negative-controls-unavailable registers the committed BAD/GOOD
## pair for the UNAVAILABLE-versus-UNSIGNALLED distinction itself, anchored
## against #1117 implemented naively - a gate that lets work through cannot be
## trusted on a clean tree alone, and this one is the gate that decides whether
## the other gates can fail.
## verify-coverage: gate negative-controls - runs the whole registered control battery with --strict --allow-unavailable; UNAVAILABLE (a gate whose own tool is absent) is named as unexamined rather than failed, every other non-PASS verdict reds (#1117)
negative-controls:
	@python3 scripts/check-negative-controls.py --strict --allow-unavailable

## MUTATION-PROBING THE REGISTERED BATTERIES (issue #970), AND WHY IT IS NOT IN
## `verify`. ADR 0008's committed-control bound is necessary and not sufficient:
## an instrument is a stack of protections, one end-to-end case travels only its
## own path, and every other protection can be deleted with the battery still
## green. This target breaks each DECLARED protection in turn and requires a
## control to fail.
##
## It is excluded from `verify` for the same reason `negative-controls` is, and
## one more. The same reason: the batteries it drives need gitleaks and jq on
## PATH, so a host missing either fails for an environment reason rather than a
## repository one. The extra reason: each mutation runs a whole battery, so this
## costs roughly (mutations + 1) battery runs, which is a wall-clock profile
## `verify` should not inherit on every invocation.
##
## It runs under `uv` deliberately. `{python}` in a manifest's declared battery
## resolves to THIS interpreter, and a battery needing the project's dependencies
## - the #953 prototype needs pytest - finds none in the sandbox, which holds
## tracked files only and therefore has no .venv for a runner-resolution walk to
## find. Under the system interpreter that battery reports every case UNKNOWN,
## which is an environment fact scored as a battery failure.
## verify-coverage: excluded mutation-probe - each mutation runs a whole battery, and those batteries need gitleaks and jq on PATH exactly as `negative-controls` does; CI runs it with --strict in its own step (#970)
mutation-probe:
	@uv run --extra dev python scripts/mutation-probe.py --strict

## Vendored delegated-driver core (issue #1011)
## `/codex:auto`, `/qwen:auto` and `/gemma:auto` describe ONE lifecycle, rendered
## from templates/delegated-driver-core.md into each driver between the
## delegated-core markers. The three used to carry three copies, which is how
## #774's "the Step 2 report reads like a checkpoint and is not one" existed in
## all three at once - and codex's copy had already drifted ~60 lines ahead of
## the other two by the time this landed.
##
## In `verify` AND in CI `validate` (unlike `oscillation`, which needs git):
## stdlib-only, offline, git-free, so the slim CI image gives the same verdict.
## Reconcile drift by editing the template or the per-driver values file and
## re-running `make delegated-core-write` - never by editing a rendered region.
## controls/delegated-core-vendor registers the committed BAD/GOOD pair, since a
## gate that lets work through cannot be trusted on a clean tree alone.

## verify-coverage: gate delegated-core-check - the vendored delegated-driver core still matches its template
delegated-core-check:
	@python3 scripts/delegated-core-vendor.py check

## verify-coverage: utility delegated-core-write - renders the delegated-driver core; it issues no verdict
delegated-core-write:
	@python3 scripts/delegated-core-vendor.py --write

## Derive the docs/scripts.md entry POPULATION from scripts/ (issue #1013).
## The inventory was hand-maintained and unchecked, so a script could be added
## and its entry simply never written - 17 of 68 were in that state - while six
## test modules quoted sentences out of the file as if it were complete. Only
## the SET is mechanical; the prose per entry stays hand-written.
##
## In `verify` AND in CI `validate` (unlike `oscillation`, which needs git):
## stdlib-only, offline, git-free, so the slim CI image gives the same verdict.
## controls/scripts-inventory registers the committed BAD/GOOD cases, since a
## gate that lets work through cannot be trusted on a clean tree alone.

## verify-coverage: gate scripts-inventory-check - docs/scripts.md covers every file in scripts/
scripts-inventory-check:
	@python3 scripts/scripts-inventory-check.py

## ADR 0008's census MEMBERSHIP, derived from scripts/ (issue #1060)
## #1002 made the census COUNT derived; the ROWS stayed hand-appended, and
## nothing noticed when an instrument was never added. Eight were in neither
## table when this landed - among them counter-model-receipt.py, which then
## shipped carrying #1047 and #1048, the defect class the census exists to
## bound. An instrument in neither table is not counted as uncontrolled; it is
## not counted at all.
## Reds on ENUMERATION, never on coverage: an enumerated row with no control
## stays green. A gate that failed 59 rows on day one would be switched off
## inside a week, which is the oscillation ADR 0009 predicts.
## stdlib-only, offline, git-free, so the slim CI image gives the same verdict.
## controls/instrument-census registers the committed BAD/GOOD cases.

## verify-coverage: gate instrument-census-check - ADR 0008's census accounts for every file in scripts/
instrument-census-check:
	@python3 scripts/instrument-census-check.py

## Host-surface declaration (issue #1139). Derives which install-path helpers
## must declare a host surface, so a managed environment can compose a defer-set
## from CPP's own code rather than from a hand-maintained list that goes stale.
## Inline host writes in the cpp command documents (issue #1132). The seam is
## total today; without this it is partial the first time someone adds a printf.
## verify-coverage: gate cpp-host-writes-check - no inline host write in /cpp:init or /cpp:update
cpp-host-writes-check:
	@python3 scripts/check-cpp-host-writes.py

## verify-coverage: gate host-surface-check - every helper reachable from /cpp:init and /cpp:update declares its host surfaces
host-surface-check:
	@python3 scripts/host-surface-check.py

## Emit the declaration as JSON, for a consumer to read. Issues no verdict.
## verify-coverage: utility host-surface-manifest - emits the declared host surfaces as JSON; it issues no verdict
host-surface-manifest:
	@python3 scripts/host-surface-check.py --manifest

## verify-coverage: gate consolidation-ledger-check - the Codex-consolidation ledger is complete against its committed snapshot
consolidation-ledger-check:
	@python3 scripts/check-consolidation-ledger.py

## Enforce the CLAUDE.md "guard tests that shell out to git/docker/gitleaks"
## directive (issue #602). It failed three times as prose (#451, #489, #577)
## precisely because it is invisible locally: this box HAS git, so the red
## pipeline was the only messenger. Stdlib-only source analysis, so it gives the
## same verdict here as in the slim CI image. Also asserted by
## tests/test_test_binary_guards.py, which is what runs it in CI `validate`.

## verify-coverage: gate binary-guards-check - tests that shell out to git/docker/gitleaks guard the binary
binary-guards-check:
	@python3 scripts/check-test-binary-guards.py

## Enforce the CLAUDE.md "a negative-condition fixture asserts its own
## precondition" directive (issue #697). A fixture that builds an absence
## indirectly can create one broader than it intended, and the fail-open
## assertions it then makes - nothing printed, exit code unchanged - are also
## what a completely broken fixture produces, so the green run is
## unfalsifiable from the outside (#695). Stdlib-only source analysis. Also
## asserted by tests/test_negative_fixture_preconditions.py, which is what runs
## it in CI `validate` - and which MUTATES the one real instance to prove this
## gate can still fire, since a clean tree alone cannot show that.

## verify-coverage: gate negative-fixture-check - every constructed absence asserts its own precondition
negative-fixture-check:
	@python3 scripts/check-negative-fixture-preconditions.py

## Keep always-loaded repository guidance bounded, resolvable, and behaviorally
## findable after narrative moves to owned documentation (issue #724).

## verify-coverage: gate agents-md-budget-check - the Codex agent-context file stays inside its word budget
## ci: runs agents-md-budget-check
## The budget is set by what it FORBIDS (#1071): AGENTS.md is a pointer to
## CLAUDE.md plus what is Codex-specific, and the failure it exists to prevent is
## someone restating CLAUDE.md's Core Directives block in it - the second copy the
## thin design removes. That block is 389 words; the legitimate content is 308; a
## copy lands at 697. 450 admits the content with room to grow and refuses the
## copy by 247. A cap a duplicate fits under is decoration.
agents-md-budget-check:
	@python3 scripts/check-claude-md-budget.py AGENTS.md --budget 450

## verify-coverage: gate claude-md-budget-check - always-loaded guidance stays inside its word budget
## ci: runs claude-md-budget-check
claude-md-budget-check:
	@python3 scripts/check-claude-md-budget.py

## verify-coverage: gate claude-md-links-check - every path CLAUDE.md names resolves
claude-md-links-check:
	@python3 scripts/check-claude-md-links.py

## verify-coverage: gate version-consistency-check - the version is the same everywhere it is written
version-consistency-check:
	@python3 scripts/check-version-consistency.py

## verify-coverage: gate unicode-dashes-check - no unicode dashes in the tree
unicode-dashes-check:
	@python3 scripts/check-unicode-dashes.py

## verify-coverage: gate co-authored-by-trailer-check - the Co-Authored-By trailer names a real model
co-authored-by-trailer-check:
	@python3 scripts/check-co-authored-by-trailer.py

## verify-coverage: gate claude-md-behavior-check - CLAUDE.md directives stay behaviorally findable
claude-md-behavior-check:
	@python3 scripts/check-claude-md-behavior.py

## Documentation (used by /flow:auto and /flow:finish)

## verify-coverage: utility update_docs - prints what to regenerate; it issues no verdict
update_docs:
	@echo "Run /documentation:c4 to regenerate C4 architecture diagrams"
	@echo "Review CLAUDE.md and README.md for accuracy"

## Bootstrap dependency check (admin-only prerequisites)

## verify-coverage: excluded bootstrap-check - admin-only host prerequisites - a fact about this box, and a CI container legitimately has none
bootstrap-check:
	@scripts/bootstrap-check.sh

## Drift detection (compare host-installed artifacts against repo templates)

## verify-coverage: excluded drift-check - compares host-installed artifacts against repo templates and REPAIRS them; it inspects and writes to HOME
drift-check:
	@scripts/drift-detect.sh --fix

## Deploy (used by /flow:deploy and /flow:auto Step 9)
## CPP ships no deployable services as of #469 - the second-opinion MCP server
## runs from its own external repo (github.com/cooneycw/mcp-second-opinion) and
## CPP consumes it via .mcp.json. This target is an informative no-op so the
## flow deploy path stays intact without a container runtime.

## verify-coverage: utility deploy - an informative no-op since #469; CPP ships no container services
deploy:
	@echo "Nothing to deploy: CPP no longer ships container services (issue #469)."
	@echo "The second-opinion MCP server runs from its own repo:"
	@echo "  https://github.com/cooneycw/mcp-second-opinion"
	@echo "Run that server, then point .mcp.json at it (localhost or Tailscale). See /cpp:init."

## Woodpecker CLI setup

## verify-coverage: utility setup-woodpecker-cli - installs the Woodpecker CLI on this box
setup-woodpecker-cli:
	@scripts/setup-woodpecker-cli.sh

## Codex skill generation (single-source -> per-harness, issue #555). The
## deprecated flat codex/prompts/ surface (issue #446) and its codex-prompts /
## codex-prompts-check targets were retired at the #556 cutover.

## verify-coverage: gate codex-skills-check - codex/skills/ still matches what the generator produces from .claude/commands/
codex-skills-check:
	@python3 scripts/codex-skill-sync.py --check

## verify-coverage: utility codex-skills - regenerates codex/skills/; it issues no verdict
codex-skills:
	@python3 scripts/codex-skill-sync.py --write

## Topic skill package, provenance, reference, and managed-install parity (#720)

## verify-coverage: excluded skills-check - compares host-local managed installs under .agents/skills, so its verdict depends on this box. The CANONICAL half is in this gate, via tests/test_skills_check.py::test_real_repo_skills_are_valid_without_host_managed_state in `make test`; the managed-mirror half is consumed only by install-drift.sh
skills-check:
	@python3 scripts/skills-check.py

## verify-coverage: utility codex-init - regenerates and installs the Codex skills
codex-init:
	@python3 scripts/codex-skill-sync.py --write --install

## Install the checked-in skills to ~/.codex/skills WITHOUT regenerating them -
## the host-refresh path used by /cpp:init Tier 5 and /cpp:update Step 7.9,
## where the repo copy is already current and CI-gated (issue #575). Prunes
## managed orphans at the destination; never touches unmarked or dotted entries.
## verify-coverage: utility codex-install - installs the checked-in Codex skills to ~/.codex/skills
codex-install:
	@python3 scripts/codex-skill-sync.py --install

## Vendored eli5-gate core (issue #591)
## The canonical home of the /flow:eli5 necessity gate is cooneycw/eli5-gate;
## CPP vendors its core between the eli5-core markers. Two complementary checks:
## eli5-check is OFFLINE and a hard gate (did the local core get edited out of
## band?); eli5-drift is a NETWORK, fail-open advisory (did upstream move?).
## Neither subsumes the other - a manifest cannot notice upstream moving.

## verify-coverage: excluded eli5-check - an offline hard gate consumed by the CI eli5-vendor-check step; nothing about it needs the network or this host
eli5-check:
	@python3 scripts/eli5-vendor.py

## verify-coverage: excluded eli5-drift - a network advisory against the canonical eli5-gate repo
eli5-drift:
	@python3 scripts/eli5-vendor.py --upstream

## verify-coverage: utility eli5-revendor - re-fetches and re-pins the vendored core; it issues no verdict
eli5-revendor:
	@python3 scripts/eli5-vendor.py --revendor

## CPP-OWNED project-next engine (issues #723, #1069). The engine was vendored
## from codex-power-pack until #1069 and is CPP's outright now, so the offline
## check no longer asks "does this match upstream" - there is no upstream. It
## asks whether the engine can change without its consumer-facing contract
## version changing. `project-next-drift` and `project-next-revendor` were
## retired with the transfer: both fetched from codex-power-pack, which is going
## private and dormant, and lib/vendor.py carries no auth to reach it after that.

## verify-coverage: gate project-next-check - the owned project-next engine still matches its pins and its contract version
project-next-check:
	@python3 scripts/project-next-ownership.py check

## verify-coverage: utility project-next-repin - recomputes the ownership pins after a deliberate engine change; it issues no verdict
project-next-repin:
	@python3 scripts/project-next-ownership.py --repin

## Shared permission-risk taxonomy (issue #576)
## classify-tool-risk.py (canonical) and the copy vendored inline in
## hook-permission-census.sh must agree on the safety-critical sets. tool-risk-check
## is the CI shape (--strict, exit 1 on drift; same command the tool-risk-drift
## Woodpecker step runs); tool-risk-drift is the advisory local shape that reports
## and exits 0.

## verify-coverage: excluded tool-risk-check - the strict shape, consumed by the CI tool-risk-drift step; nothing about it needs the network or this host
tool-risk-check:
	@python3 scripts/tool-risk-drift.py --strict

## verify-coverage: excluded tool-risk-drift - the advisory local shape of the same taxonomy comparison
tool-risk-drift:
	@python3 scripts/tool-risk-drift.py

## Branch-protection posture (issue #577, ADR 0004)
## The posture is DATA (.claude/branch-protection.json), not a click-path: check
## diffs live protection against it, apply PUTs it idempotently. Deliberately NOT
## a CI gate - reading protection needs an admin-scoped token the pipeline does
## not have - so this is a local check, run when protection may have moved.

## verify-coverage: excluded branch-protection-check - reading live protection needs an admin-scoped GitHub token the pipeline does not have
branch-protection-check:
	@bash scripts/branch-protection.sh check

## verify-coverage: utility branch-protection-apply - PUTs the recorded posture; it issues no verdict
branch-protection-apply:
	@bash scripts/branch-protection.sh --apply

## verify-coverage: utility branch-protection-show - prints the live posture; it issues no verdict
branch-protection-show:
	@bash scripts/branch-protection.sh --show

## Retired host surfaces (issue #575)
## Directories in HOME that CPP once generated into and no longer does. The
## generator gets deleted from the repo; the copies it already wrote stay put,
## unmaintained and silently loading. Curated by .claude/retired-surfaces.yaml,
## gated on the GENERATED marker, and reversible - prune MOVES files to a
## timestamped sibling rather than deleting them.

## verify-coverage: excluded host-surfaces-check - inspects retired generator output in HOME - a fact about this box
host-surfaces-check:
	@python3 scripts/retired-surface-prune.py --check

## verify-coverage: utility host-surfaces-plan - a dry run of the prune; it issues no verdict
host-surfaces-plan:
	@python3 scripts/retired-surface-prune.py --plan

## verify-coverage: utility host-surfaces-prune - moves retired host surfaces aside; it issues no verdict
host-surfaces-prune:
	@python3 scripts/retired-surface-prune.py --prune --all

## Installed-helper drift guard + retired marketplace report (issues #622/#662)
## Compares installed ~/.claude/scripts helpers with the checkout through #663;
## also names cached families pending `/plugin uninstall <family>@cpp` without
## reviving the retired marketplace clone/cache parity walk.
## Deliberately NOT part of `make verify`: it inspects HOME, so it is a local
## check about THIS box, and a CI container legitimately has no install at all.

## verify-coverage: excluded install-drift-check - compares installed ~/.claude/scripts helpers with the checkout - a fact about this box
install-drift-check:
	@scripts/install-drift.sh

## verify-coverage: utility install-drift-list - lists the installed helpers; it issues no verdict
install-drift-list:
	@scripts/install-drift.sh --list

## Common-memory harness (issue #433): links scripts/cpp-memory onto PATH and
## installs the hand-authored Codex /cpp-memory prompt. Idempotent. Wired into
## /cpp:init Tier 5 and /cpp:update Step 7.9 (issue #575) - before that it was
## documented as re-runnable from /cpp:update but never actually invoked.
## verify-coverage: utility memory-harness - links scripts/cpp-memory onto PATH; it issues no verdict
memory-harness:
	@bash scripts/install-memory-harness.sh

## Utilities

## verify-coverage: utility clean - removes caches; it issues no verdict
clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
