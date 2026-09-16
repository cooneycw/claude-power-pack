#!/usr/bin/env sh
# Run ONE case of the npm-global-upgrade control (issue #1022).
#
# WHAT THIS PINS, AND WHAT IT MUST NOT. It pins WHICH `npm`, `node` and harness
# binaries exist, by prepending the case's `bin/` to PATH, and it hands the
# fixtures a private scratch directory. It does NOT compute, inspect, rewrite or
# influence the verdict: the real `scripts/npm-global-upgrade.sh` runs unmodified
# over the fixture environment, and its stdout, stderr and exit code pass
# straight through. A runner that decided anything would be the control
# certifying itself.
#
# ONE RUNNER FOR EVERY CASE, deliberately. Per-case runners are per-case logic,
# and per-case logic is where a case quietly stops testing what its name says.
# Every difference between the cases lives in `cases/<name>/bin/`, where a
# reviewer can diff them against each other.
#
# WHY THE SCRATCH DIRECTORY IS `mktemp -d` AND NOT A PATH IN THE REPO. The
# `good-upgraded` fixture has to make the harness report a DIFFERENT version
# after the install than before it, which needs state shared between two stub
# programs. Writing that state into the case directory would leave an untracked
# file under `controls/`, which `check-negative-controls.py` reports as UNTRACKED
# - correctly, since a green from files that are not in the repository does not
# survive a clone. A fixed `/tmp` name would instead be a shared mutable path
# that two concurrent runs race on. `mktemp -d` is neither.
#
# PATH IS PREPENDED, NOT REPLACED. The gate needs `grep`, `cut`, `tr` and
# `head`; a replaced PATH would remove those too and the case would fail for
# reasons unrelated to what it is testing - the #695 constructed-absence trap
# this repository has a gate for.
set -u

GATE="${1:?run-case.sh: the gate path is required}"
CASE_DIR="${2:?run-case.sh: the case directory is required}"

[ -f "$GATE" ] || { echo "run-case.sh: no gate at '$GATE'" >&2; exit 3; }
[ -d "$CASE_DIR/bin" ] || { echo "run-case.sh: no bin/ in case '$CASE_DIR'" >&2; exit 3; }

STATE=$(mktemp -d "${TMPDIR:-/tmp}/npm-global-upgrade-case.XXXXXX") || {
    echo "run-case.sh: could not create a scratch directory" >&2; exit 3; }
trap 'rm -rf "$STATE"' EXIT INT TERM

NPM_UPGRADE_FIXTURE_STATE="$STATE"
export NPM_UPGRADE_FIXTURE_STATE

PATH="$CASE_DIR/bin:$PATH"
export PATH

sh "$GATE" --package fixture-pkg --binary fixture-harness --label "fixture lane"
rc=$?
exit "$rc"
