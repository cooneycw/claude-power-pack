#!/bin/sh
# Runs one install-drift.sh orphan-axis case (nit store #864).
#
# install-drift.sh is steered by CPP_INSTALL_DRIFT_CHECKOUT and
# CPP_INSTALL_DRIFT_HOME; the runner substitutes {gate} and {case} into an argv
# with no environment control, so this wrapper supplies both from the case's own
# committed trees.
#
# WHY THIS WRAPPER SETS AN EXIT CODE AT ALL, which is the one thing here worth
# reading carefully. The framework reads a non-zero exit as detection, and only
# believes it when the gate ALSO emitted its declared signal - a crash exits
# non-zero too. But an orphan is REPORTED and deliberately does NOT change
# install-drift's verdict: it mirrors the Codex arm, whose own orphans have
# never fed VERDICT=drift, because an orphan is a thing to notice and not a
# reason to refuse. A report-only axis therefore cannot be expressed in the
# framework's exit convention without an adapter.
#
# THE ADAPTER USES TWO INDEPENDENT CHANNELS SO IT CANNOT GRADE ITS OWN HOMEWORK.
# The exit code below is keyed on the JSON `helpers_orphaned` COUNT, while the
# runner's detect_signal is keyed on the human-readable line that NAMES members.
# Those come from different code paths in the gate. If they ever disagree -
# a count with no names, or names with a zero count - the exit says detection
# and the signal check does not, and the framework reports UNSIGNALLED rather
# than a verdict. A single-channel adapter keyed on the same line the runner
# reads would agree with itself by construction and prove nothing.
#
# It is also why the count alone is not the signal: over a real install
# directory two candidate predicates both yield 91 entries and are DISJOINT on
# two members, so a count can be right while the set is wrong. The names are
# what a reader can check; the count is only the trigger.
set -u
gate="$1"
case_dir="$2"

if ! command -v bash >/dev/null 2>&1; then
    echo "INSTALL_DRIFT_CONTROL: unavailable - bash is not installed"
    exit 2
fi

# Cases are COMMITTED read-only fixtures and this gate only reads, so nothing is
# copied. The gate is given the case's own checkout/ and home/, never the
# developer's real ~/.claude/scripts - a control whose verdict depended on host
# state would be contaminated by the machine it runs on, and this axis is
# precisely a statement about host state.
report=$(CPP_INSTALL_DRIFT_CHECKOUT="$case_dir/checkout" \
         CPP_INSTALL_DRIFT_HOME="$case_dir/home" \
         bash "$gate" 2>/dev/null)
report_status=$?
# The report is echoed through UNCHANGED so the runner reads the gate's own
# words, not this wrapper's summary of them.
printf '%s\n' "$report"
if [ "$report_status" -ne 0 ]; then
    echo "INSTALL_DRIFT_CONTROL: unavailable - the gate exited $report_status on the report path"
    exit 2
fi

json=$(CPP_INSTALL_DRIFT_CHECKOUT="$case_dir/checkout" \
       CPP_INSTALL_DRIFT_HOME="$case_dir/home" \
       bash "$gate" --json 2>/dev/null) || json=""

# Channel B: the JSON count. May be ABSENT, and absent is not zero.
count=$(printf '%s' "$json" | sed -n 's/.*"helpers_orphaned":\([0-9][0-9]*\).*/\1/p')
# Channel A: the human report's NAMED line - the same one the runner's
# detect_signal reads. Recomputed here from the report captured above.
if printf '%s' "$report" | grep -q '^  Orphaned helpers (installed, no longer in the checkout): [^ ]'; then
    named=1
else
    named=0
fi

# THE CROSS-CHECK. "No JSON key" is doing double duty and must not: on the
# CURRENT gate it means the channel broke, but on a pre-fix ANCHOR it means the
# axis does not exist - which is the blindness the anchor is vendored to
# demonstrate. The second channel is what separates them, and that is the whole
# reason there are two. Without this the anchor reported "tool absent" and the
# framework correctly refused to confirm it had MISSED anything.
if [ -z "$count" ]; then
    if [ "$named" -eq 1 ]; then
        echo "INSTALL_DRIFT_CONTROL: unavailable - the report NAMES an orphan but the --json channel has no helpers_orphaned key"
        exit 2
    fi
    # No axis at all, or an axis that found nothing: either way this run did
    # NOT detect, which is the honest answer and the one a blind anchor owes.
    echo "INSTALL_DRIFT_CONTROL_ORPHANED: none (no helpers_orphaned key; report names none)"
    exit 0
fi
if [ "$count" -gt 0 ] && [ "$named" -eq 0 ]; then
    echo "INSTALL_DRIFT_CONTROL: unavailable - --json counts $count orphan(s) and the report names none"
    exit 2
fi
if [ "$count" -eq 0 ] && [ "$named" -eq 1 ]; then
    echo "INSTALL_DRIFT_CONTROL: unavailable - the report names an orphan and --json counts zero"
    exit 2
fi
echo "INSTALL_DRIFT_CONTROL_ORPHANED: $count"
[ "$count" -eq 0 ] || exit 1
exit 0
