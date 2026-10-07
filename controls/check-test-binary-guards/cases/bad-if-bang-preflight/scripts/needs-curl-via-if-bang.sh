#!/usr/bin/env bash
# Fixture helper for the check-test-binary-guards negative control (issue
# #1407). A TOP-LEVEL `if ! command -v curl; then ... exit; fi` preflight,
# whose own "if !" text (preceding the match on the same line) was
# misclassified as evidence of NESTING rather than the preflight's own
# condition-opening syntax - and a later, stderr-silenced use that is
# unconditionally safe (the preflight already exited) rather than "fail-soft".
set -euo pipefail
if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required" >&2
    exit 1
fi
RESULT=$(curl -s http://example.invalid 2>/dev/null)
echo "$RESULT"
