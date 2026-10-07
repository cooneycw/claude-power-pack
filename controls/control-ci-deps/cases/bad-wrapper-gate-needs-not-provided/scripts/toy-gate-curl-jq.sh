#!/bin/sh
# NEGATIVE-CONTROL: controls/toy
# Hard-requires BOTH curl and jq via top-level, unconditionally-exiting
# preflights - the shape `binaries_in_script` recognises (issue #1407). Only
# curl is staged by this case's wrapper and claimed as provided; jq is not,
# and must still be reported as needed - pinning that a wrapper's provided
# claim narrows the gate's needs by exactly what it verifies, never by
# switching the whole gate off.
if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required" >&2
    exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "jq is required" >&2
    exit 1
fi
curl -s http://example.invalid 2>/dev/null | jq .
echo "toy-gate: ok - 0 finding(s)"
exit 0
