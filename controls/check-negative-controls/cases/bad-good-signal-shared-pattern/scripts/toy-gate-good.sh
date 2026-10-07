#!/bin/sh
# A toy gate with TWO distinct clean answers sharing one good_exit (issue
# #1395's actual shape: controls/counter-model-enrolment's six GOOD cases
# each expect a different clean line at the SAME exit code). The registered
# "good-accepted" case below is deliberately given the OTHER case's marker
# file, so it answers "not-enrolled" while still exiting clean - the
# known-bad input for check-negative-controls' own per-case good_signal.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
if [ -f "$root/trip" ]; then
    echo "toy-gate: FINDING"
    exit 1
fi
if [ -f "$root/not-enrolled" ]; then
    echo "toy-gate: ok (not-enrolled)"
    exit 0
fi
echo "toy-gate: ok (accepted)"
exit 0
