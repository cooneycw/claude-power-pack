#!/usr/bin/env sh
# KNOWN-BAD: exiting on a verdict the map does not carry. The module must
# REFUSE rather than fall through to the good exit, which is what a hand-written
# `case ... *) exit 0` does.
. "$GATE_LIB"
gate_map ok=0 finding=1
gate_exit unknown
