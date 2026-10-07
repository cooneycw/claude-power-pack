#!/bin/sh
# Runs one install-drift.sh UNLINKED-axis case (issue #1401).
#
# install-drift.sh is steered by CPP_INSTALL_DRIFT_CHECKOUT and
# CPP_INSTALL_DRIFT_HOME; the runner substitutes {gate} and {case} into an argv
# with no environment control, so this wrapper supplies both from the case's own
# committed trees - same seam controls/install-drift/run-case.sh already uses.
#
# THE SAME ADAPTER, FOR THE SAME REASON: HELPERS_UNLINKED is report-only and
# deliberately does not move VERDICT (it only joins the early-skip guard,
# mirroring HELPERS_ORPHANED), so a positive finding cannot be read off the
# gate's own exit code. This wrapper derives its own exit from the JSON
# `helpers_unlinked` count, cross-checked against the human report's NAMED
# line - the same two-independent-channels discipline as the orphan control,
# for the same reason: a single channel keyed on the line the runner also
# reads would agree with itself by construction and prove nothing.
set -u
gate="$1"
case_dir="$2"

if ! command -v bash >/dev/null 2>&1; then
    echo "INSTALL_DRIFT_CONTROL: unavailable - bash is not installed"
    exit 2
fi

report=$(CPP_INSTALL_DRIFT_CHECKOUT="$case_dir/checkout" \
         CPP_INSTALL_DRIFT_HOME="$case_dir/home" \
         bash "$gate" 2>/dev/null)
report_status=$?
printf '%s\n' "$report"
if [ "$report_status" -ne 0 ]; then
    echo "INSTALL_DRIFT_CONTROL: unavailable - the gate exited $report_status on the report path"
    exit 2
fi

json=$(CPP_INSTALL_DRIFT_CHECKOUT="$case_dir/checkout" \
       CPP_INSTALL_DRIFT_HOME="$case_dir/home" \
       bash "$gate" --json 2>/dev/null) || json=""

# Channel B: the JSON count. May be ABSENT (pre-#1401 anchor, no such key), and
# absent is not zero.
count=$(printf '%s' "$json" | sed -n 's/.*"helpers_unlinked":\([0-9][0-9]*\).*/\1/p')
# Channel A: the human report's NAMED line.
if printf '%s' "$report" | grep -q '^  Unlinked helpers (in scripts/, not yet installed - run /cpp:update): [^ ]'; then
    named=1
else
    named=0
fi

if [ -z "$count" ]; then
    if [ "$named" -eq 1 ]; then
        echo "INSTALL_DRIFT_CONTROL: unavailable - the report NAMES an unlinked helper but the --json channel has no helpers_unlinked key"
        exit 2
    fi
    echo "INSTALL_DRIFT_CONTROL_UNLINKED: none (no helpers_unlinked key; report names none)"
    exit 0
fi
if [ "$count" -gt 0 ] && [ "$named" -eq 0 ]; then
    echo "INSTALL_DRIFT_CONTROL: unavailable - --json counts $count unlinked helper(s) and the report names none"
    exit 2
fi
if [ "$count" -eq 0 ] && [ "$named" -eq 1 ]; then
    echo "INSTALL_DRIFT_CONTROL: unavailable - the report names an unlinked helper and --json counts zero"
    exit 2
fi
echo "INSTALL_DRIFT_CONTROL_UNLINKED: $count"
[ "$count" -eq 0 ] || exit 1
exit 0
