#!/usr/bin/env sh
# KNOWN-GOOD: the ordinary path. A flag with its value, a contract line, a
# mapped verdict. Separates a working module from one wedged at "refuse".
. "$GATE_LIB"
gate_map ok=0 finding=1 unknown=2
set -- --root /tmp
gate_arg_value --root "$#" "${2-}"
gate_emit PROBE ok "root=[$GATE_VALUE]"
gate_exit ok
