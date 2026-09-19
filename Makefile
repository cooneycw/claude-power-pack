.PHONY: test lint format typecheck verify shellcheck secret-scan tools-check \
	scripts-inventory-check instrument-census-check dep-audit dep-audit-selftest dep-audit-capture \
       oscillation update_docs clean \
       bootstrap-check drift-check deploy setup-woodpecker-cli \
       codex-init codex-skills codex-skills-check codex-install \
       eli5-check eli5-drift eli5-revendor \
       project-next-check project-next-drift project-next-revendor \
       tool-risk-check tool-risk-drift \
       branch-protection-check branch-protection-apply branch-protection-show \
       host-surfaces-check host-surfaces-plan host-surfaces-prune memory-harness \
       binary-guards-check negative-fixture-check claude-md-budget-check \
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
			printf '  but `make test` runs controls that invoke these scanners DIRECTLY and has no such fallback,\n'; \
			printf '  so controls/shellcheck-gate and controls/secret-scan will report UNSIGNALLED there.\n'; \
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
tools-version-check:
	@scripts/tools-version-check.sh

## WHAT VERSION IS THE EXECUTED COPY? (issue #1029). Every install-parity check
## compares against THE CHECKOUT and none of them can say how current that is;
## on 2026-09-15 it was 21 commits behind main while every session ran from it.
toolchain-provenance:
	@scripts/toolchain-provenance.sh

## WHO IS HOLDING THE CHECKOUT RIGHT NOW? (issue #1029). Names the pids running
## DELETED files from this tree (a pull did not reach them) and the pids holding
## current ones (a pull now hot-swaps instruments under a running gate). `clear`
## is the declared safe moment for the pull.
checkout-readers:
	@scripts/checkout-readers.sh

## Quality gates (used by /flow:finish)

lint:
	uv run --extra dev ruff check .

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
test:
	@set -e; workers="$$(sh scripts/pytest-workers.sh)"; \
		uv run --extra dev pytest -n "$$workers"

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

dep-audit: dep-audit-selftest
	@python3 scripts/dependency-audit.py

## The LIVE positive control, run BEFORE the audit above on purpose. A scan that
## cannot see prints the same clean line as a clean tree, so this audits two
## committed fixtures first - a 2019 PyYAML pin that must report, a clean pin
## that must not - and the real verdict is only issued afterwards.
dep-audit-selftest:
	@python3 scripts/dependency-audit.py --selftest

## Record this tree's raw pip-audit reports, for building or refreshing the
## offline control fixtures under controls/dependency-audit/cases/.
dep-audit-capture:
	@python3 scripts/dependency-audit.py --capture dependency-audit-capture.json

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
oscillation:
	@python3 scripts/check-oscillation.py

verify: tools-check lint test typecheck shellcheck oscillation \
	binary-guards-check negative-fixture-check \
	claude-md-budget-check claude-md-links-check claude-md-behavior-check \
	project-next-check delegated-core-check \
	scripts-inventory-check instrument-census-check \
	consolidation-ledger-check \
	version-consistency-check unicode-dashes-check co-authored-by-trailer-check

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

delegated-core-check:
	@python3 scripts/delegated-core-vendor.py check

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

instrument-census-check:
	@python3 scripts/instrument-census-check.py

consolidation-ledger-check:
	@python3 scripts/check-consolidation-ledger.py

## Enforce the CLAUDE.md "guard tests that shell out to git/docker/gitleaks"
## directive (issue #602). It failed three times as prose (#451, #489, #577)
## precisely because it is invisible locally: this box HAS git, so the red
## pipeline was the only messenger. Stdlib-only source analysis, so it gives the
## same verdict here as in the slim CI image. Also asserted by
## tests/test_test_binary_guards.py, which is what runs it in CI `validate`.

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

negative-fixture-check:
	@python3 scripts/check-negative-fixture-preconditions.py

## Keep always-loaded repository guidance bounded, resolvable, and behaviorally
## findable after narrative moves to owned documentation (issue #724).

claude-md-budget-check:
	@python3 scripts/check-claude-md-budget.py

claude-md-links-check:
	@python3 scripts/check-claude-md-links.py

version-consistency-check:
	@python3 scripts/check-version-consistency.py

unicode-dashes-check:
	@python3 scripts/check-unicode-dashes.py

co-authored-by-trailer-check:
	@python3 scripts/check-co-authored-by-trailer.py

claude-md-behavior-check:
	@python3 scripts/check-claude-md-behavior.py

## Documentation (used by /flow:auto and /flow:finish)

update_docs:
	@echo "Run /documentation:c4 to regenerate C4 architecture diagrams"
	@echo "Review CLAUDE.md and README.md for accuracy"

## Bootstrap dependency check (admin-only prerequisites)

bootstrap-check:
	@scripts/bootstrap-check.sh

## Drift detection (compare host-installed artifacts against repo templates)

drift-check:
	@scripts/drift-detect.sh --fix

## Deploy (used by /flow:deploy and /flow:auto Step 9)
## CPP ships no deployable services as of #469 - the second-opinion MCP server
## runs from its own external repo (github.com/cooneycw/mcp-second-opinion) and
## CPP consumes it via .mcp.json. This target is an informative no-op so the
## flow deploy path stays intact without a container runtime.

deploy:
	@echo "Nothing to deploy: CPP no longer ships container services (issue #469)."
	@echo "The second-opinion MCP server runs from its own repo:"
	@echo "  https://github.com/cooneycw/mcp-second-opinion"
	@echo "Run that server, then point .mcp.json at it (localhost or Tailscale). See /cpp:init."

## Woodpecker CLI setup

setup-woodpecker-cli:
	@scripts/setup-woodpecker-cli.sh

## Codex skill generation (single-source -> per-harness, issue #555). The
## deprecated flat codex/prompts/ surface (issue #446) and its codex-prompts /
## codex-prompts-check targets were retired at the #556 cutover.

codex-skills-check:
	@python3 scripts/codex-skill-sync.py --check

codex-skills:
	@python3 scripts/codex-skill-sync.py --write

## Topic skill package, provenance, reference, and managed-install parity (#720)

skills-check:
	@python3 scripts/skills-check.py

codex-init:
	@python3 scripts/codex-skill-sync.py --write --install

## Install the checked-in skills to ~/.codex/skills WITHOUT regenerating them -
## the host-refresh path used by /cpp:init Tier 5 and /cpp:update Step 7.9,
## where the repo copy is already current and CI-gated (issue #575). Prunes
## managed orphans at the destination; never touches unmarked or dotted entries.
codex-install:
	@python3 scripts/codex-skill-sync.py --install

## Vendored eli5-gate core (issue #591)
## The canonical home of the /flow:eli5 necessity gate is cooneycw/eli5-gate;
## CPP vendors its core between the eli5-core markers. Two complementary checks:
## eli5-check is OFFLINE and a hard gate (did the local core get edited out of
## band?); eli5-drift is a NETWORK, fail-open advisory (did upstream move?).
## Neither subsumes the other - a manifest cannot notice upstream moving.

eli5-check:
	@python3 scripts/eli5-vendor.py

eli5-drift:
	@python3 scripts/eli5-vendor.py --upstream

eli5-revendor:
	@python3 scripts/eli5-vendor.py --revendor

## Vendored codex-power-pack project-next engine (issue #723). The offline
## per-file manifest check is a hard gate. The live upstream comparison is a
## fail-open network advisory; refresh only after reviewing upstream drift.

project-next-check:
	@python3 scripts/project-next-vendor.py check

project-next-drift:
	@python3 scripts/project-next-vendor.py --upstream

project-next-revendor:
	@python3 scripts/project-next-vendor.py --revendor

## Shared permission-risk taxonomy (issue #576)
## classify-tool-risk.py (canonical) and the copy vendored inline in
## hook-permission-census.sh must agree on the safety-critical sets. tool-risk-check
## is the CI shape (--strict, exit 1 on drift; same command the tool-risk-drift
## Woodpecker step runs); tool-risk-drift is the advisory local shape that reports
## and exits 0.

tool-risk-check:
	@python3 scripts/tool-risk-drift.py --strict

tool-risk-drift:
	@python3 scripts/tool-risk-drift.py

## Branch-protection posture (issue #577, ADR 0004)
## The posture is DATA (.claude/branch-protection.json), not a click-path: check
## diffs live protection against it, apply PUTs it idempotently. Deliberately NOT
## a CI gate - reading protection needs an admin-scoped token the pipeline does
## not have - so this is a local check, run when protection may have moved.

branch-protection-check:
	@bash scripts/branch-protection.sh check

branch-protection-apply:
	@bash scripts/branch-protection.sh --apply

branch-protection-show:
	@bash scripts/branch-protection.sh --show

## Retired host surfaces (issue #575)
## Directories in HOME that CPP once generated into and no longer does. The
## generator gets deleted from the repo; the copies it already wrote stay put,
## unmaintained and silently loading. Curated by .claude/retired-surfaces.yaml,
## gated on the GENERATED marker, and reversible - prune MOVES files to a
## timestamped sibling rather than deleting them.

host-surfaces-check:
	@python3 scripts/retired-surface-prune.py --check

host-surfaces-plan:
	@python3 scripts/retired-surface-prune.py --plan

host-surfaces-prune:
	@python3 scripts/retired-surface-prune.py --prune --all

## Installed-helper drift guard + retired marketplace report (issues #622/#662)
## Compares installed ~/.claude/scripts helpers with the checkout through #663;
## also names cached families pending `/plugin uninstall <family>@cpp` without
## reviving the retired marketplace clone/cache parity walk.
## Deliberately NOT part of `make verify`: it inspects HOME, so it is a local
## check about THIS box, and a CI container legitimately has no install at all.

install-drift-check:
	@scripts/install-drift.sh

install-drift-list:
	@scripts/install-drift.sh --list

## Common-memory harness (issue #433): links scripts/cpp-memory onto PATH and
## installs the hand-authored Codex /cpp-memory prompt. Idempotent. Wired into
## /cpp:init Tier 5 and /cpp:update Step 7.9 (issue #575) - before that it was
## documented as re-runnable from /cpp:update but never actually invoked.
memory-harness:
	@bash scripts/install-memory-harness.sh

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
