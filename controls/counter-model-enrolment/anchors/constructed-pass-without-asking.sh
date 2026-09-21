#!/usr/bin/env bash
# CONSTRUCTED ANCHOR for controls/counter-model-enrolment (issue #1171).
#
# THE INSTRUMENT AS IT STOOD BEFORE THIS ISSUE. scripts/flow-finish-gate.sh
# reached a pass verdict without ever asking whether a counter-model review was
# recorded for the branch - the string "counter-model" appeared in it exactly
# twice, both times in comments crediting a past review for finding a bug. So
# this anchor is not a hypothetical: it is the decision the real gate made, on
# every run, for the whole life of the file.
#
# WHY IT IS BLIND. It has no enrolment question to get wrong. A branch with a
# review and a branch with none produce identical output, which is the whole of
# #1171: a skipped review and a clean one are the same bytes. It therefore
# passes EVERY bad case in this control - no receipt, a skip naming a reason the
# committed set refuses, a receipt belonging to someone else's history - and
# that is what the control measures.
#
# Deliberately NOT the real gate with the enrolment block deleted. The real gate
# reaches its verdict through the Python runner or a Makefile fallback, and an
# anchor carrying all of that would score the harness rather than the decision.
# This is the decision, and the decision is "pass without asking".
#
# The live equivalent - the real gate with the integration actually removed -
# was run against these cases before this control was committed, and reported
# `skipped` (exit 4, a PASS) on all three bad cases. That run is the evidence
# the control can fail; this file is the committed form of it.
echo "FLOW_FINISH_GATE: skipped"
exit 4
