#!/usr/bin/env sh
# KNOWN-BAD: using the module with no declared mapping at all. There is no good
# exit to protect, so the module must REFUSE rather than guess one.
. "$GATE_LIB"
gate_emit PROBE ok "no gate_map was declared"
gate_exit ok
