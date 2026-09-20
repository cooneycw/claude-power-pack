#!/usr/bin/env bash
# A clean .sh file, present so the gate has a normal file to count beside the
# option-like one, and so a mutated run still examines SOMETHING.
set -eu
greet() { printf "hello %s\n" "${1:-world}"; }
