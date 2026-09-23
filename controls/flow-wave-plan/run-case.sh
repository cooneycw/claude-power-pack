#!/bin/sh
# Case runner for controls/flow-wave-plan (#1189).
#
# WHY AN ADAPTER. The planner's own exit codes already carry its verdict (4 = a
# recorded ruling holds an issue), but a case has to supply TWO files - the issue
# set and the ledger - and the harness passes one directory. This joins them and
# passes the planner's exit through unchanged.
#
# IT DECIDES NOTHING. The case directories hold an issues.json and a
# verdicts.json and nothing else; no expected verdict, no test id, no count
# appears in either. The discriminator is the planner's OWN answer, which is why
# a blind planner produces a different one from the same bytes.
set -u
case_dir="$1"
gate="$2"

out=$(python3 "$gate" "$case_dir/issues.json" --verdicts "$case_dir/verdicts.json" \
        --in-flight '' 2>&1)
status=$?

# A gate that fell over is NOT a detection (#946). The planner uses 0 (plan
# produced, nothing held), 4 (a recorded ruling holds an issue) and 2 (it could
# not read its inputs). Only 0 and 4 are answers.
case "$status" in
  0) exit 0 ;;
  4) printf '%s\n' "$out"
     echo "FLOW_WAVE_PLAN_CONTROL: finding - a recorded ruling holds an issue"
     exit 1 ;;
  2)
     # EXIT 2 IS TWO DIFFERENT ANSWERS AND THE CONTROL MUST NOT CONFLATE THEM.
     #
     # "cannot read verdict ledger" on THIS input is the defect under test, not
     # an environment failure: the planner was handed a readable ledger and
     # refused it because one entry names a subject it cannot plan against. It
     # did not report the hold, so it MISSED - which is exactly what the blind
     # anchor is committed to demonstrate. Scoring that `unavailable` would
     # record the pre-fix planner as unable to look, when it looked and threw
     # the file away.
     #
     # Any other exit 2 - an unreadable issues file, a missing interpreter - is
     # a gate that could not run, and stays unavailable. A crash must never
     # score as a detection (#946); it must not score as a MISS either, or a
     # broken anchor would certify a control it never exercised.
     if printf '%s' "$out" | grep -q 'cannot read verdict ledger'; then
         printf '%s\n' "$out"
         exit 0
     fi
     echo "FLOW_WAVE_PLAN_CONTROL: unavailable - the planner could not read its inputs" >&2
     printf '%s\n' "$out" >&2
     exit 3 ;;
  *) echo "FLOW_WAVE_PLAN_CONTROL: unavailable - the planner exited $status" >&2
     printf '%s\n' "$out" >&2
     exit 3 ;;
esac
