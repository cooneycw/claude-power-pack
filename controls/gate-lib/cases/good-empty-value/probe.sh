#!/usr/bin/env sh
# KNOWN-GOOD, and the one that pins WHICH QUESTION the refusal asks. An EMPTY
# value was SUPPLIED here; it is not a value MISSING. A module deciding on
# `[ -n "$2" ]` - two live idioms in this tree do - conflates the two and
# rejects this, so this case is what keeps the decision on the COUNT.
. "$GATE_LIB"
gate_map ok=0 finding=1 unknown=2
set -- --root ""
gate_arg_value --root "$#" "${2-}"
gate_emit PROBE ok "root is the empty string, and it was supplied"
gate_exit ok
