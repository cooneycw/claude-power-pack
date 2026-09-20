#!/usr/bin/env bash
# CONSTRUCTED anchor for controls/flow-finish-gate-derivation (issues #1152, #1163).
#
# No historical article carries this defect: no released gate ever deduplicated
# gates at all, so none of them can be blind to a bad derivation. What this
# reproduces is the OBVIOUS WRONG FIX - treat the PRESENCE of a `verify:` target
# as covering lint, test and typecheck, instead of DERIVING which of them that
# target actually names.
#
# The distinction is the entire subject. A repository whose `verify:` runs only
# SOME of the three gets the others silently dropped under this rule, and an
# aggregate cannot fail on a check it never runs - so the gate reports ok over a
# broken gate that nothing executed.
#
# Deliberately NOT the real gate with one line changed: the real gate reaches
# its verdict through the Python runner, and an anchor carrying all of that
# would be measuring the harness rather than the decision. This reproduces the
# decision and prints the same marker.
set -uo pipefail

if [[ ! -f Makefile ]]; then
    echo "FLOW_FINISH_GATE: skipped"
    exit 4
fi

# THE BLIND RULE: a `verify:` target exists, therefore the three quality gates
# are covered. No prerequisite list is ever read.
if grep -q '^verify:' Makefile 2>/dev/null; then
    if make verify >/dev/null 2>&1; then
        echo "FLOW_FINISH_GATE: ok"
        exit 0
    fi
    echo "FLOW_FINISH_GATE: fail"
    exit 1
fi

for target in lint test typecheck; do
    grep -q "^${target}:" Makefile 2>/dev/null || continue
    if ! make "$target" >/dev/null 2>&1; then
        echo "FLOW_FINISH_GATE: fail"
        exit 1
    fi
done
echo "FLOW_FINISH_GATE: ok"
exit 0
