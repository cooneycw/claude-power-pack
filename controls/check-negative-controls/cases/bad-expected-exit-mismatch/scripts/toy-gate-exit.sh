#!/bin/sh
# A toy gate with TWO distinct findings sharing one detect_signal (issue
# #1395's actual shape: ^ATTRIBUTION-(FINDING|UNKNOWN): matches both of
# counter-model-reviewer-attribution's real bad verdicts). The registered
# "bad" case below is deliberately given the WRONG trigger file, so it
# drifts to the other finding while staying in the same BAD bucket - the
# known-bad input for check-negative-controls' own expected_exit check.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
if [ -f "$root/trip-b" ]; then
    echo "toy-gate: FINDING (reason b)"
    exit 2
fi
if [ -f "$root/trip-a" ]; then
    echo "toy-gate: FINDING (reason a)"
    exit 1
fi
echo "toy-gate: ok"
exit 0
