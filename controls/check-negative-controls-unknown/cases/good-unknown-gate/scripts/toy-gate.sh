#!/bin/sh
# A toy gate that REFUSES, in the words its manifest declares, when the input
# defeats it - and reports a finding or a clean run when it does not.
#
# Three branches, because every gate in this tree has three: it found something,
# it found nothing, or it could not look. The third fires on THIS INPUT rather
# than on this machine, which is what makes it a property a case may register
# (issue #1129) and what separates it from the tool-absent fixture next door in
# controls/check-negative-controls-unavailable.
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
    echo "toy-gate: UNKNOWN - 0 subject file(s) under '$root'; 0 examined is not 0 findings." >&2
    echo "toy-gate: this is not a pass." >&2
    exit 3
fi
if [ "$hits" -gt 0 ]; then
    echo "toy-gate: FINDING - $count subject file(s) examined, $hits reported." >&2
    exit 1
fi
echo "toy-gate: ok - $count subject file(s) examined, 0 findings."
