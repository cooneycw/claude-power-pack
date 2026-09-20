#!/bin/sh
# NEGATIVE-CONTROL: controls/toy
# The registration the BATTERY discovers. This gate resolves its register
# through the battery's own discover(), so a fixture without a marker has
# no registered control at all - which is the point of sharing the rule.
# A gate that needs nothing the slim image lacks: `sh` runs it, and it shells
# out to nothing at all.
echo "toy-gate: ok - 0 finding(s)"
exit 0
