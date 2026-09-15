#!/bin/sh
# A toy gate that REPORTS a finding on its known-bad input, which is what a
# working gate does. This tree is the known-good input for
# check-negative-controls: the harness should report PASS on it.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="$2"; shift 2 ;; *) shift ;; esac; done
if [ -f "$root/trip" ]; then
    echo "toy-gate: FINDING in known-bad input"
    exit 1
fi
echo "toy-gate: clean"
