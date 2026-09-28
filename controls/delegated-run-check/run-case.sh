#!/bin/sh
# Case runner for controls/delegated-run-check (issue #1265, ADR 0008 row 13).
#
# The gate's verdict on a run is STATUS, but a failed tool call is deliberately
# NOT a failed run (a denied call is the fence working) - it is a COUNT,
# DELEGATED_RUN_TOOL_ERRORS, which is the one fact that tells a caller to go and
# look. A gate that stops seeing failed calls therefore does not change STATUS;
# it prints `TOOL_ERRORS: 0`, which reads exactly like "checked, none". So the
# FINDING here is the count: non-zero is the known-bad input detected.
#
# The cases name no answer: each is a payload file, and the discriminator is the
# gate's own TOOL_ERRORS line. Nothing is executed but the gate itself - no
# network, no model, no chmod (CI runs as root; nothing here depends on uid).
#
# Markers:
#   unavailable - python3 is not installed   the gate parses JSONL with python3
#   cannot-run - ...                         anything else; matches no declared
#                                            signal, so it is reported loudly
set -u
case_dir="$1"
gate="$2"

command -v python3 >/dev/null 2>&1 || { echo "DELEGATED_RUN_CONTROL: unavailable - python3 is not installed"; exit 3; }
[ -f "$case_dir/payload.jsonl" ] || { echo "DELEGATED_RUN_CONTROL: cannot-run - case has no payload.jsonl"; exit 3; }

out=$(bash "$gate" "$case_dir/payload.jsonl" 0 --lane gemma 2>&1)
status=$?
# 0 success / 1 failure are the gate's verdicts; anything else never answered.
case "$status" in
    0|1) : ;;
    *) printf '%s\n' "$out"; echo "DELEGATED_RUN_CONTROL: cannot-run - the gate exited $status"; exit 3 ;;
esac
count=$(printf '%s\n' "$out" | sed -n 's/^DELEGATED_RUN_TOOL_ERRORS: //p' | head -1)
case "$count" in
    ''|*[!0-9]*) printf '%s\n' "$out"; echo "DELEGATED_RUN_CONTROL: cannot-run - no TOOL_ERRORS count in the contract"; exit 3 ;;
esac
printf '%s\n' "$out"
if [ "$count" -gt 0 ]; then
    echo "DELEGATED_RUN_CONTROL: finding - $count failed tool call(s) counted"
    exit 1
fi
exit 0
