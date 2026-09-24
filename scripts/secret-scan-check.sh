#!/bin/sh
# The secret-scan negative control's gate (issue #935).
#
# WHY IT RELOCATES, which is the whole design. `.gitleaks.toml`'s allowlist is
# PATH-SCOPED, and the committed fixture sits at an exempt path so the repo-wide
# `make secret-scan` stays green. Scanning the fixture WHERE IT LIVES therefore
# finds nothing - the carve-out that keeps the repo clean would blind the control
# that the carve-out exists to make honest. Measured on the CI-pinned v8.30.1:
#
#   same bytes at controls/secret-scan/cases/…   0 findings
#   same bytes relocated to a scratch path       1 finding
#
# So this copies the case OUT of the exempt path and scans the copy with the
# SHIPPED config. One config, one ruleset, the original claim intact: it proves
# the gate the repository actually runs catches this shape. The pair also proves
# more than a removal check would - that the carve-out is real AND that it is
# narrowly scoped to that path rather than blinding the gate generally.
#
# POPULATION, stated because it is not the only one: this uses `--no-git`, the
# flag `make secret-scan` passes, so it proves the WORKING-TREE population. CI
# runs gitleaks WITHOUT `--no-git` and therefore scans git history. This control
# does not cover that population.
#
#: NEGATIVE-CONTROL: controls/secret-scan
#
# Usage: secret-scan-check.sh --root <dir>
set -u

# THE SHARED GATE MODULE (issue #1127, 2 of 4). This gate is the one that was
# ALREADY RIGHT: its `[ $# -ge 2 ]` on the line above the shift is the fifth
# idiom in the tree and the only one that decided on the COUNT rather than on
# the emptiness of the candidate - which is the semantics #1126 chose for
# `gate_arg_value`. So `--root ""` was accepted here before this migration and
# is accepted after it; nothing about this gate's handling of an empty value is
# new, and it is the reason the other three now agree with it rather than the
# other way round.
#
# A line-scoped grep for `${2:?}` reads this block as unguarded. It was not.
# Read the block, not the matched line.
#
# Adopts `gate_map` and `gate_arg_value`. NOT `gate_emit`: this gate's findings
# are gitleaks' own `RuleID:` lines, which its control keys on, and its other
# output is `secret-scan-control: ...` prose - neither is a `KEY: verdict`
# contract line, and inventing one would change what the control reads.
# `${0%/*}`, NEVER `$(dirname "$0")`. `dirname` is an external binary, and
# sourcing the module is the FIRST thing these gates do - so a PATH without it
# left the gate unable to load at all, and therefore unable to say UNKNOWN in
# exactly the environment where UNKNOWN is the answer. Caught by
# `tests/test_shellcheck_stage.py`, which constructs that PATH deliberately and
# which this slice may not edit; that is what the byte-identical constraint is
# for. Parameter expansion forks nothing and needs nothing on PATH.
_gate_lib_dir=${0%/*}
[ "$_gate_lib_dir" = "$0" ] && _gate_lib_dir=.
# shellcheck disable=SC1091  # gate-lib.sh is resolved at run time and linted as its own file (#972)
. "$_gate_lib_dir/gate-lib.sh"

gate_map clean=0 findings=1 usage=2 unavailable=3

die() { echo "secret-scan-control: $1" >&2; exit 2; }

ROOT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --root) gate_arg_value "$1" "$#" "${2-}"; ROOT=$GATE_VALUE; shift 2 ;;
        *) die "unknown argument: $1" ;;
    esac
done
[ -n "$ROOT" ] || die "--root is required"
[ -d "$ROOT" ] || die "no such case directory: $ROOT"

HERE=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
CONFIG="$HERE/../.gitleaks.toml"
[ -f "$CONFIG" ] || die "shipped config not found at $CONFIG"

# A gate that cannot run must not exit 0 - `good_exit` is 0, so a missing
# scanner would otherwise read as a clean verdict. This is the `unknown` state.
command -v gitleaks >/dev/null 2>&1 || {
    echo "secret-scan-control: gitleaks is not installed - the scan could NOT be performed." >&2
    echo "  This is unchecked, not clean." >&2
    exit 3
}

WORK=$(mktemp -d) || die "could not create a scratch directory"
trap 'rm -rf "$WORK"' EXIT
cp -R "$ROOT"/. "$WORK"/ || die "could not relocate the case"

# A control that COPIES is one sed away from testing something else, so the
# copy is proven identical before it is scanned.
#
# UNCOVERED, and measured rather than assumed: a mutation deleting this check
# left all 11 tests green. No INPUT to this script can make the copy differ from
# the source - this script does the copying - so the assertion guards a future
# EDIT to the copy logic above it, and nothing exercises it. Keeping it with the
# gap stated beats keeping it while implying it is tested; the alternative, a
# case containing a symlink so `cp -R` and `sha256sum` disagree, buys coverage
# of a shape no real fixture has.
for f in "$ROOT"/*; do
    [ -f "$f" ] || continue
    b=$(basename "$f")
    a_sum=$(sha256sum "$f" | cut -d' ' -f1)
    b_sum=$(sha256sum "$WORK/$b" | cut -d' ' -f1)
    [ "$a_sum" = "$b_sum" ] || die "relocated copy differs from the committed fixture: $b"
done

gitleaks detect --source "$WORK" --config "$CONFIG" --no-git --verbose
