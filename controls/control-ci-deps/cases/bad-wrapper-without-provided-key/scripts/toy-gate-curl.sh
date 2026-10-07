#!/bin/sh
# NEGATIVE-CONTROL: controls/toy
# Hard-requires curl via a top-level, unconditionally-exiting preflight - the
# shape `binaries_in_script` recognises (issue #1407).
if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required" >&2
    exit 1
fi
curl -s http://example.invalid 2>/dev/null
echo "toy-gate: ok - 0 finding(s)"
exit 0
