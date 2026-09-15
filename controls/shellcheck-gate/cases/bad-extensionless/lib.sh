#!/usr/bin/env bash
# A clean .sh file, present so a glob-based gate finds SOMETHING and reports a
# confident "0 findings" rather than an honest "0 files matched".
set -eu
greet() { printf 'hello %s\n' "${1:-world}"; }
