#!/usr/bin/env bash
# Fixture helper for the check-test-binary-guards negative control (issue
# #1407, counter-model finding 2). The `! command -v curl` preflight sits on
# an `elif` branch, not an `if`/`while`/`until` opener - it runs only when the
# FIRST branch's own condition was false, so curl is genuinely OPTIONAL here:
# a true first branch skips the preflight and the fallback entirely, and the
# script still does its job. `CONDITION_OPENER_RE` must not treat this
# column-zero `elif` as an unconditional entry point the way it treats a
# genuine `if`/`while`/`until` opener - that was the exact over-broad
# classification the counter-model review caught. The later curl use is
# stderr-silenced AND `|| true`, so it is independently fail-soft either way;
# this fixture's whole point is the preflight classification, not the use.
set -uo pipefail
if command -v wget >/dev/null 2>&1; then
    :
elif ! command -v curl >/dev/null 2>&1; then
    echo "no downloader found" >&2
    exit 1
fi
curl --version >/dev/null 2>&1 || true
