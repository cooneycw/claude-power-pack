#!/bin/sh
# A toy REPORTER: it has no non-zero verdict except "I could not look". There
# is no input that makes it report a finding, which is the whole reason a
# reporter cannot register a BAD case.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
if [ -f "$root/opaque" ]; then
    echo "toy-gate: UNKNOWN - this input cannot be examined"
    exit 2
fi
echo "toy-gate: clean"
