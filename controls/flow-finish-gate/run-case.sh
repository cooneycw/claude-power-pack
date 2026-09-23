#!/bin/sh
# ONE case runner shared by all six controls/flow-finish-gate* registrations.
#
# WHY IT LIVES HERE. It is shared, not owned by this control, but a new file
# under scripts/ would owe a census row in ADR 0008 - a file this lane does not
# hold - and a seventh controls/ directory for one script would be worse. The
# five siblings invoke it by this path; keep it here and keep them pointing at
# it rather than copying it, which is how six near-identical inline invocations
# drifted apart in the first place.
#
# WHAT IT FIXES. The six controls used to `cd` into their case IN PLACE, inside
# this repository, so when the gate asked git "what branch am I on" git answered
# about the ENCLOSING repository - a fact the fixture never chose and cannot
# control. The gate then looked for a counter-model receipt recorded on that
# branch, found none, and a case designed to be GOOD failed.
#
# THE VARIABLE IS ATTACHMENT, not the branch and not the commit. Measured at one
# sha (cbd7dcf), same case, three head states:
#     attached to a feature branch -> fail (counter-model line missing)
#     DETACHED at the same sha     -> ok
#     attached to main, same sha   -> fail (counter-model line missing)
# So `main` fails too, permanently, and CI - which checks out a SHA and is
# therefore always detached - can never see any of it.
#
# THE MECHANISM IS NOT INVENTED HERE. controls/flow-finish-gate-derivation and
# -resume already copied their cases to a `mktemp -d` and ran there, and they
# are exactly the two of six that passed both attached and detached. This makes
# that mechanism shared and explicit instead of duplicated in two invocations
# and missing from four.
#
# ONLY THE GOOD CASES WERE EVER CONTAMINATED: a failing gate step short-circuits
# before the counter-model check, so every BAD case still redded correctly in
# place. That asymmetry is why the fix is isolation rather than a looser signal.
#
# THE CPP-DIR MODE IS A PARAMETER, because it is load-bearing and it DIFFERS
# across the six. Measured while writing this: collapsing them all to the
# derived value turned `good-all-green` from `ok` into `warn` - a silent
# behaviour change in a control's own subject, caused by the fix. The three
# modes that exist in tree:
#   empty     flow-finish-gate            (FLOW_GATE_CPP_DIR=)
#   case-cpp  -declared-gates, -plan-reconciliation, -subsumption ($case/cpp)
#   derived   -derivation, -resume        (two levels up from the gate)
set -u
case_dir="$1"
gate="$2"
cpp_mode="${3:-derived}"

_cpp_dir() {
    # $1 = the directory the gate will run in (the case, or its isolated copy)
    case "$cpp_mode" in
        empty)    printf '' ;;
        case-cpp) printf '%s/cpp' "$1" ;;
        derived)  _d="${gate%/*}"; printf '%s' "${_d%/*}" ;;
        *)        echo "FLOW_FINISH_GATE_CONTROL: unavailable - unknown cpp mode '$cpp_mode'" >&2
                  printf '' ;;
    esac
}

if ! command -v bash >/dev/null 2>&1; then
    echo "FLOW_FINISH_GATE_CONTROL: unavailable - bash is not installed"
    exit 2
fi

# THE DELIBERATE REAL-REPO PATH (marker file, not a second invocation, because
# `invocation` is control-level and cannot vary per case). An isolated fixture
# can DRIFT from how the gate really runs - trading a false red for a false
# GREEN, which is strictly worse than the red this fixes - so at least one case
# stays on the real path on purpose. The marker makes that choice visible in the
# case DIRECTORY as well as in its name, so neither can be mistaken for
# leftovers.
if [ -f "$case_dir/RUN-ON-THE-REAL-REPO-PATH" ]; then
    cd "$case_dir" || {
        echo "FLOW_FINISH_GATE_CONTROL: unavailable - could not enter $case_dir"
        exit 2
    }
    # SAY WHICH PATH WAS TAKEN. Without this the marker is unobservable from the
    # verdict - a BAD case reds on either path, so a marker that silently stopped
    # working would leave a case NAMED for the real path while quietly running
    # isolated, which is the drift this case exists to catch, wearing the costume
    # of the guard against it.
    echo "FLOW_FINISH_GATE_CONTROL_PATH: real-repo"
    PATH="$case_dir/bin:$PATH" FLOW_GATE_CPP_DIR="$(_cpp_dir "$case_dir")" bash "$gate"
    exit $?
fi

# UNAVAILABLE, NEVER CLEAN, when the isolated context cannot be built. A battery
# that silently runs fewer cases is the unscanned-reads-as-clean failure this
# repository has a verdict for, and the failure modes here are real: a full or
# read-only TMPDIR, or a copy that cannot complete.
work=$(mktemp -d "${TMPDIR:-/tmp}/flow-finish-gate-control.XXXXXX") || {
    echo "FLOW_FINISH_GATE_CONTROL: unavailable - could not create an isolated directory"
    exit 2
}
trap 'rm -rf "$work"' EXIT INT TERM
if ! cp -R "$case_dir"/. "$work"/; then
    echo "FLOW_FINISH_GATE_CONTROL: unavailable - could not populate the isolated directory"
    exit 2
fi

# THE ISOLATION IS THE LOCATION. `mktemp -d` lands under TMPDIR, which is outside
# every git repository, so `git rev-parse` finds nothing and the gate takes the
# same path it takes on every CI run. Verified rather than assumed: `cd $(mktemp
# -d) && git rev-parse --show-toplevel` reports "not a git repository".
#
# REFUSE TO RUN IF THAT IS NOT TRUE. A TMPDIR that happens to sit inside a
# checkout would silently restore the exact coupling this removes, and the case
# would go green while measuring the wrong thing - which is worse than the red.
if (cd "$work" && git rev-parse --git-dir >/dev/null 2>&1); then
    echo "FLOW_FINISH_GATE_CONTROL: unavailable - TMPDIR is inside a git repository,"
    echo "  so the isolated context is not isolated and this case would measure the"
    echo "  enclosing repository instead of its own fixture"
    exit 2
fi

cd "$work" || {
    echo "FLOW_FINISH_GATE_CONTROL: unavailable - could not enter the isolated directory"
    exit 2
}
echo "FLOW_FINISH_GATE_CONTROL_PATH: isolated"
PATH="$work/bin:$PATH" FLOW_GATE_CPP_DIR="$(_cpp_dir "$work")" bash "$gate"
