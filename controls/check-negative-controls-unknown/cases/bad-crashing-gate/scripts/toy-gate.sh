#!/bin/sh
# THE SAME toy gate as cases/good-unknown-gate, with ONE branch changed: where
# that one REFUSES, this one FALLS OVER. It dies on the unexaminable input with
# a non-zero exit and nothing that identifies a refusal.
#
# That is the whole known-bad input, and the difference is deliberately one
# branch: a fixture that differed in several ways would not establish WHICH one
# the harness is reading. A crash and a refusal both exit non-zero and both say
# nothing the detection pattern matches, so a harness that scores a registered
# UNKNOWN case on the exit code alone CANNOT tell them apart - and calls this
# gate correct. That is issue #946 re-created inside the field #1129 adds, which
# is exactly what the constructed anchor beside this tree does.
#: NEGATIVE-CONTROL: controls/toy
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
count=0
hits=0
for f in "$root"/subject-*; do
    [ -f "$f" ] || continue
    count=$((count + 1))
    if grep -q TRIP "$f"; then hits=$((hits + 1)); fi
done
if [ "$count" -eq 0 ]; then
    echo "Traceback (most recent call last):" >&2
    echo "  File \"toy-gate\", line 1, in <module>" >&2
    echo "ZeroDivisionError: division by zero" >&2
    exit 3
fi
if [ "$hits" -gt 0 ]; then
    echo "toy-gate: FINDING - $count subject file(s) examined, $hits reported." >&2
    exit 1
fi
echo "toy-gate: ok - $count subject file(s) examined, 0 findings."
