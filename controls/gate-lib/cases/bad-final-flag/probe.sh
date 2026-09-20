#!/usr/bin/env sh
# KNOWN-BAD: a value-taking flag given as the FINAL argument (#992).
# The module must REFUSE. It must not spin, and it must not substitute "".
. "$GATE_LIB"
gate_map ok=0 finding=1 unknown=2
set -- --root
gate_arg_value --root "$#" "${2-}"
gate_emit PROBE ok "parsed root=[$GATE_VALUE]"
gate_exit ok
