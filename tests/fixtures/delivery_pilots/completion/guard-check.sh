#!/usr/bin/env bash
# Run the repository's ACTUAL incidental-close guard against produced PR bodies.
#
# Extracting `Closes #N` or `Refs #N` with a regex says which reference the model
# selected. It does NOT say what would happen at the merge, because the merge helper
# refuses shapes a naive pattern never looks at - a closing keyword in a reword
# instruction, a negated form, a keyword beside an issue number in prose. So the
# selected reference is checked here by the guard that actually runs.
#
# The guard's refusal is exit 7 WITH a diagnostic. An earlier version of this harness
# reported its positive control as exit 1 and called that a pass - but that 1 came from
# `set -u` hitting an unset ALLOW_INCIDENTAL_CLOSE on the matched path, not from the
# guard refusing. A control that trips for the wrong reason proves nothing, so the flag
# is set explicitly and the control must produce exit 7 and say why.
#
# Usage: guard-check.sh <guard-source> <body-file> [<body-file> ...]
set -uo pipefail

GUARD_SRC="${1:?usage: guard-check.sh <guard-source> <body-file>...}"
shift
[ -f "$GUARD_SRC" ] || { echo "FATAL: guard source not found: $GUARD_SRC"; exit 1; }
[ "$#" -gt 0 ] || { echo "FATAL: no body files given"; exit 1; }

ALLOW_INCIDENTAL_CLOSE=0          # the guard's own opt-out, explicitly OFF
failures=0

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
for fn in _is_incidental_close_match _incidental_close_selfcheck guard_incidental_close_keywords; do
    awk -v f="^${fn}\\\\(\\\\)" '$0 ~ f, /^}/' "$GUARD_SRC" >> "$tmp"
done
grep -q '^guard_incidental_close_keywords()' "$tmp" || {
    echo "FATAL: guard not extracted from $GUARD_SRC - it moved or was renamed"; exit 1; }
# shellcheck disable=SC1090
source "$tmp"
close_keyword_scan_sources() { :; }   # arrays are supplied directly below

run_guard() {   # $1 = body; echoes "exit|first diagnostic line"
    CLOSE_SCAN_SOURCES_LOADED=1
    CLOSE_SCAN_SOURCES=(title body)
    CLOSE_SCAN_TEXTS=("fix(exports): stream in chunks" "$1")
    local out status
    out="$(guard_incidental_close_keywords 2>&1)"; status=$?
    printf '%s|%s' "$status" "$(printf '%s' "$out" | grep -m1 . || true)"
}

# POSITIVE CONTROL, proven live before any result is reported: a body carrying a
# closing reference in reword-instruction position. The guard must refuse with 7 AND
# explain itself, or this harness is not exercising the guard at all.
control="$(run_guard 'Reword any Closes #501 references before opening.')"
control_status="${control%%|*}"; control_msg="${control#*|}"
if [ "$control_status" != 7 ]; then
    echo "FATAL: positive control exited ${control_status}, expected 7 - the guard is not live here"
    exit 1
fi
if [ -z "$control_msg" ]; then
    echo "FATAL: positive control refused without a diagnostic - cannot confirm it is the guard"
    exit 1
fi
echo "positive control: exit=7  ${control_msg:0:110}"

for f in "$@"; do
    [ -s "$f" ] || { echo "FATAL: $f is missing or empty"; exit 1; }
    result="$(run_guard "$(cat "$f")")"
    status="${result%%|*}"
    printf '%-40s exit=%s\n' "$(basename "$f")" "$status"
    if [ "$status" != 0 ]; then
        echo "  TRIPPED: ${result#*|}"
        failures=$((failures + 1))
    fi
done

if [ "$failures" -gt 0 ]; then
    echo "GUARD: ${failures} body/bodies would interrupt the merge"
    exit 1
fi
echo "GUARD: control refused as expected; all $# body/bodies pass the real guard"
