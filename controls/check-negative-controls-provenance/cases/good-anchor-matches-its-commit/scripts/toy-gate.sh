#!/bin/sh
#: NEGATIVE-CONTROL: controls/toy
# toy-gate.sh - the gate as it stands now: it sees the trip file.
root=""
while [ "$#" -gt 0 ]; do case "$1" in --root) root="$2"; shift ;; esac; shift; done
if [ -e "$root/trip" ]; then echo "toy-gate: FINDING - trip file present"; exit 1; fi
exit 0
