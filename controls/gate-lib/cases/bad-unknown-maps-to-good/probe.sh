#!/usr/bin/env sh
# KNOWN-BAD: a second verdict declared at the good exit, so "could not tell"
# would render as "clean" (#1014, #800). The module must REFUSE at declaration.
. "$GATE_LIB"
gate_map ok=0 unknown=0
gate_emit PROBE ok "declared unknown=0"
gate_exit ok
