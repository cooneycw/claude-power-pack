#!/bin/sh
# A toy gate that CRASHES on its own known-bad input instead of reporting a
# finding. Pre-#946 the harness scored that as detection; #946 made it
# UNSIGNALLED. This tree is the known-bad input for check-negative-controls.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="$2"; shift 2 ;; *) shift ;; esac; done
if [ -f "$root/trip" ]; then
    exec /nonexistent-binary-so-this-crashes
fi
echo "toy-gate: clean"
