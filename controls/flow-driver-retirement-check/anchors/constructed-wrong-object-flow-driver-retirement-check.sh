#!/usr/bin/env bash
# THE CHECK THAT WAS ACTUALLY RUN, AND WHY IT WAS WRONG.
#
# This is the anchor for controls/flow-driver-retirement-check. It is NOT a past
# revision of scripts/flow-driver-retirement-check.sh - that script is new, and
# the honest "before" is not an earlier gate but the improvisation the gate
# replaces. Issue #1017 records it in one sentence:
#
#     "A check run while filing this returned 0 matching roles - but it read
#      ~/.claude/daemon/roster.json, which is the WRONG OBJECT."
#
# That is reconstructed here. It reads a plausible roster path, finds no role
# carrying the driver, and reports `RETIREMENT: clear`. It does so on EVERY
# input, because it never consults the object that holds the answer - so it
# misses a live role, misses an undetermined one, and misses a host with no
# registry at all, while agreeing with the real gate on the one case that
# genuinely is clear. Its zeros look exactly like real ones.
#
# WHY THIS IS THE RIGHT ANCHOR RATHER THAN THE COMMITTED PROSE PROCEDURE.
# #934's procedure DOES catch a live role and DOES catch an undetermined one -
# it was written carefully and it is right about two of the three. Vendoring it
# would make this control INERT on those two cases while proving only the third.
# The blindness worth pinning is the one that actually occurred and that the
# whole three-outcome vocabulary exists to prevent: a check pointed at an object
# that cannot contain the answer, reporting absence with total confidence.
#
# A control whose anchor misses every known-bad input is what demonstrates the
# cases discriminate at all. Re-reading the real gate would only ever show what
# it MEANT.
set -u

DRIVER=""
while [ $# -gt 0 ]; do
    case "$1" in
        --driver)       DRIVER="${2:-}"; shift 2 ;;
        --wave)         shift 2 ;;
        --registry-dir) shift 2 ;;   # accepted and IGNORED - that is the defect
        --helper)       shift 2 ;;
        *)              shift ;;
    esac
done

# The wrong object.
#
# THE PATH IS OVERRIDABLE, AND THAT IS NOT A CONVENIENCE (counter-model finding,
# 2026-09-16). Reading `$HOME/.claude/daemon/roster.json` unconditionally made
# this anchor's blindness depend on AMBIENT HOST STATE: that file exists on the
# machine this was written on, and a daemon roster that ever carried a matching
# `driver` key would make the anchor BLOCK every fixture and score the control
# INERT - "the anchor caught the known-bad input" - for a reason nobody had
# changed. An anchor that can stop being blind without an edit is not an anchor.
# So the control and the tests pin it at a committed roster fixture; the default
# stays the real path, because the real path is what this reconstructs.
ROSTER="${FLOW_DRIVER_RETIREMENT_ANCHOR_ROSTER:-${HOME:-/nonexistent}/.claude/daemon/roster.json}"

MATCHED=0
if [ -f "$ROSTER" ] && command -v jq >/dev/null 2>&1; then
    MATCHED="$(jq -r --arg d "$DRIVER" \
        '[ .. | objects | select(.driver? == $d) ] | length' "$ROSTER" 2>/dev/null || echo 0)"
fi

if [ "$MATCHED" != "0" ]; then
    echo "RETIREMENT: blocked ($MATCHED role(s) on '$DRIVER')"
    exit 1
fi
echo "RETIREMENT: clear for '$DRIVER' across 1 wave(s)"
exit 0
