#!/bin/sh
# A toy gate that goes SILENT on its own known-bad input: it exits non-zero and
# prints nothing that identifies a finding OR an absent tool. That is
# UNSIGNALLED, and it must STAY UNSIGNALLED after #1117.
#
# Its manifest DECLARES an unavailable_signal, which is the whole point of this
# fixture. A harness that consulted the field loosely - "non-zero and nothing I
# recognise, so the tool was probably missing" - would excuse this gate. The
# declaration is present and the gate simply does not say the thing, so the
# honest answer is unchanged.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
if [ -f "$root/trip" ]; then
    exec /nonexistent-binary-so-this-crashes
fi
echo "toy-gate: clean"
