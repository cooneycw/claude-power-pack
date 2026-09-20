#!/bin/sh
# A toy gate whose own tool is not installed, on EVERY input. It says so in the
# words its manifest declares, and exits non-zero because a gate that could not
# look must never exit like a clean run.
#
# EVERY input, not just the known-bad one, and that is not decoration: a binary
# that is absent is absent for every case. A fixture reporting unavailability on
# one case and running cleanly on another would be caught by the harness's own
# contradiction check and reported UNRESOLVED - correctly, because that is what a
# pattern matching something OTHER than a missing tool looks like.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
echo "toy-gate: UNAVAILABLE - the toy tool is not installed, so nothing was examined." >&2
echo "toy-gate: this is not a pass." >&2
exit 3
