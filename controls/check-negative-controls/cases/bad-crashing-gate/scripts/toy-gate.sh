#!/bin/sh
# A toy gate that CRASHES on its own known-bad input instead of reporting a
# finding. Pre-#946 the harness scored that as detection; #946 made it
# UNSIGNALLED. This tree is the known-bad input for check-negative-controls.
#: NEGATIVE-CONTROL: controls/toy
root=""
# `${2:?}` rather than `"$2"`: a dangling `--root` made `shift 2` fail,
# shifting nothing, and the loop spun forever. Kept to one line - a fixture
# that grows helpers stops being the small readable specimen it exists to be.
#
# STRICTER THAN WHAT IT REPLACES, so the reversal trigger lives here (#936):
# `:?` fires on unset OR NULL, so `--root ""` now exits where it used to set
# root="" and carry on. WHAT MOVES IT BACK: any control.json `invocation` whose
# --root argument can render empty - checkable by reading the manifests, not by
# waiting for a report. Today every one passes `{case}`, a path, so the strict
# form costs nothing. If one ever does, `:?` is the wrong guard and this becomes
# an explicit `[ -n ]` test that distinguishes ABSENT from EMPTY.
while [ $# -gt 0 ]; do case "$1" in --root) root="${2:?--root needs a value}"; shift 2 ;; *) shift ;; esac; done
if [ -f "$root/trip" ]; then
    exec /nonexistent-binary-so-this-crashes
fi
echo "toy-gate: clean"
