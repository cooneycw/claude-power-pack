#!/bin/sh
# Frozen blind artifact for the toy gate.
#
# It COUNTS its subjects - so it refuses an empty population exactly as the
# current gate does, which is what anchor-sanity on the UNKNOWN case requires -
# but it never INSPECTS them, so it misses the known-bad input. Blind in one
# named way and identical in every other, which is the property an anchor has to
# have for the demonstration to isolate anything.
root=""
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
count=0
for f in "$root"/subject-*; do
    [ -f "$f" ] || continue
    count=$((count + 1))
done
if [ "$count" -eq 0 ]; then
    echo "toy-gate: UNKNOWN - 0 subject file(s) under '$root'; 0 examined is not 0 findings." >&2
    echo "toy-gate: this is not a pass." >&2
    exit 3
fi
echo "toy-gate: ok - $count subject file(s) examined, 0 findings."
