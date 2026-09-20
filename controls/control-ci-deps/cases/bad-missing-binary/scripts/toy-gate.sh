#!/bin/sh
# NEGATIVE-CONTROL: controls/toy
# The registration the BATTERY discovers. This gate resolves its register
# through the battery's own discover(), so a fixture without a marker has
# no registered control at all - which is the point of sharing the rule.
# HARD-REQUIRES git, in the shape `binaries_in_script` recognises: no
# `command -v git` preflight declaring the absence survivable, and at least one
# use that is not fail-soft. This is the real failure - a control whose cases
# were bare git repositories - reduced to its smallest form.
REV=$(git rev-parse HEAD)
echo "toy-gate: 1 finding(s) at $REV"
exit 1
