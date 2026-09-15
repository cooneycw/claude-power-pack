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

die() { echo "secret-scan-control: $1" >&2; exit 2; }

ROOT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --root)
            [ $# -ge 2 ] || die "--root requires a value"
            ROOT="$2"; shift 2 ;;
        *) die "unknown argument: $1" ;;
    esac
done
[ -n "$ROOT" ] || die "--root is required"
[ -d "$ROOT" ] || die "no such case directory: $ROOT"

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
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
