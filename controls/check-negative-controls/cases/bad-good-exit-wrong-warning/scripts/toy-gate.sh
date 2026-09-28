#!/bin/sh
# A toy gate whose CLEAN answer is a warning (exit 3), like the finish gate's
# `warn`, and which says WHICH warning. The registered GOOD case below carries
# `otherwarn`: same exit code, different reason. A harness that honours the
# manifest's `good_signal` must not score that GOOD (issue #1350). This tree is
# the known-bad input for check-negative-controls.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
if [ -f "$root/trip" ]; then
    echo "toy-gate: FINDING"
    exit 1
fi
if [ -f "$root/otherwarn" ]; then
    echo "toy-gate: warn (other reason)"
    exit 3
fi
echo "toy-gate: warn (expected reason)"
exit 3
