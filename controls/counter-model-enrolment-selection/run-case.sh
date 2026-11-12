#!/bin/sh
# Case runner for controls/counter-model-enrolment-selection (issue #1707).
#
# Each case is a `setup.sh` that builds a small repository whose branch carries
# MORE THAN ONE counter-model receipt. The gate is run there in finish mode and
# its own verdict and exit status are passed straight through: the subject is
# which receipt the enrolment check judges.
#
# The gate is staged in an isolated directory with the CURRENT gate-lib beside
# it, so an anchor (the pre-#1707 gate script) runs against the same library
# and the only variable is the gate script. No runner and no Makefile: with a
# usable receipt the verdict is `skipped` (exit 4), which is this control's
# good exit; a receipt the gate refuses reds it through the counter-model line.
set -u
case_dir="$1"
gate="$2"
here=$(cd "$(dirname "$0")" && pwd)
repo_scripts="$here/../../scripts"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac

say_unavailable() { echo "CM_ENROLMENT_SELECTION_CONTROL: unavailable - $1"; exit 9; }
command -v bash >/dev/null 2>&1 || say_unavailable "bash is not installed"
command -v git >/dev/null 2>&1 || say_unavailable "git is not installed"
command -v python3 >/dev/null 2>&1 || say_unavailable "python3 is not installed"
[ -f "$case_dir/setup.sh" ] || say_unavailable "case supplies no setup.sh"
[ -f "$repo_scripts/gate-lib.sh" ] || say_unavailable "gate-lib.sh not found beside the gate's sources"
[ -f "$repo_scripts/counter-model-receipt.py" ] || say_unavailable "counter-model-receipt.py not found"

work=$(mktemp -d "${TMPDIR:-/tmp}/cm-enrolment-selection.XXXXXX") || say_unavailable "no isolated directory"
trap 'rm -rf "$work"' EXIT INT TERM
mkdir -p "$work/scripts" "$work/repo" "$work/tmp"
cp "$gate" "$work/scripts/flow-finish-gate.sh" || say_unavailable "could not stage the gate"
cp "$repo_scripts/gate-lib.sh" "$work/scripts/" || say_unavailable "could not stage gate-lib.sh"
[ -f "$repo_scripts/coordination-admission.sh" ] && cp "$repo_scripts/coordination-admission.sh" "$work/scripts/"
cp "$case_dir/setup.sh" "$work/repo/setup.sh" || say_unavailable "could not stage the case"
cd "$work/repo" || say_unavailable "could not enter the isolated directory"
if ! sh ./setup.sh >/dev/null 2>&1; then
    say_unavailable "the case's setup.sh failed"
fi
env -u CPP_KYLE_FULL_SUITE_ACTIVE -u CPP_FLOW_FINISH_GATE_STATUS_FILE \
    FLOW_GATE_CPP_DIR="" TMPDIR="$work/tmp" \
    CPP_COORDINATION_ADMISSION_FILE="$work/no-coordination-admission" \
    CM_RECEIPT_HELPER="$repo_scripts/counter-model-receipt.py" \
    bash "$work/scripts/flow-finish-gate.sh"
exit $?
