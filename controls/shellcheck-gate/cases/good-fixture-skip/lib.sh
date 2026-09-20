#!/usr/bin/env bash
# A clean .sh file, so the gate has a real file to count and does not fall into
# its "0 matched" UNKNOWN branch on this tree.
set -eu
greet() { printf "hello %s\n" "${1:-world}"; }
