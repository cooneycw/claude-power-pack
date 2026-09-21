#!/usr/bin/env bash
# CONSTRUCTED ANCHOR for controls/flow-finish-gate-resume (issue #1166).
#
# It reproduces the TEMPTING FIX - the one #1166's own body prefers and the
# wave overruled: on resume, settle every NOT_RUN record from the PERSISTED
# map. The record carries `not_run_reason` naming the aggregate, so the
# relationship is reconstructable without asking make anything; if that named
# aggregate then passes, call the gate subsumed and report ok.
#
# WHY THAT IS BLIND. The premise of a resume is that the failure was FIXED, and
# the fix may have changed the Makefile. When `verify` no longer lists `lint` on
# the resumed tree, nothing runs lint - and settling from the map records lint
# `subsumed` by an aggregate that never touched it. Green, over a broken check
# nobody executed. That is #1165's defect re-created by the repair for #1166's
# false NEGATIVE, which is exactly the shape a committed case exists to catch.
#
# Deliberately NOT the real gate with one line changed: the real gate reaches
# its verdict through the Python runner, and an anchor carrying all of that
# would measure the harness rather than the decision. This is the decision.
#
# It is blind to `bad-makefile-changed-between-runs` and agrees with the fixed
# gate on `good-fail-fix-resume`, which is what the register requires of it.
set -u

# Phase 1 + phase 2, exactly as the case's own driver arranges them: run the
# plan, let it fail at the aggregate, swap the Makefile, run again.
if [ ! -f .anchor-phase1 ]; then
    touch .anchor-phase1
    make verify >/dev/null 2>&1 || true
    [ -f Makefile.phase2 ] && cp Makefile.phase2 Makefile
fi

# THE WRONG SETTLEMENT. The previous run recorded lint/test/typecheck not-run
# and named `verify`; the aggregate passes now, so they are called subsumed -
# WITHOUT asking whether this tree's `verify` still runs them.
if make verify >/dev/null 2>&1; then
    # WARN, NOT OK, AND EXIT 3 - because the wrong fix would reach exactly the
    # same non-failing verdict the correct gate reaches on the GOOD case:
    # security_scan is still carried across a changed tree in a non-git case
    # tree, so `tree_verified` is false either way. Emitting `ok`/0 here made
    # the register score UNRESOLVED rather than blind - it could not tell a
    # MISS from a crash, since 0 is not this control's good_exit. The anchor
    # has to miss in the same currency the control judges in.
    echo "SUBSUMED: lint test typecheck - settled from the persisted map"
    echo "FLOW_FINISH_GATE: warn (carried, unverified: security_scan)"
    echo "FLOW_FINISH_GATE_EXIT=3" >&2
    exit 3
fi

echo "FLOW_FINISH_GATE: fail"
echo "FLOW_FINISH_GATE_EXIT=1" >&2
exit 1
