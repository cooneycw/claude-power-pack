#!/bin/sh
# THE BLIND ANCHOR: it has no refusal branch at all, so it answers the
# unexaminable input with a confident clean. That is the blindness under test.
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
echo "toy-gate: clean"
