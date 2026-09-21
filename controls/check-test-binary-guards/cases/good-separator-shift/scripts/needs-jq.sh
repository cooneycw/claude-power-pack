#!/usr/bin/env bash
# Fixture helper for the check-test-binary-guards negative control.
#
# It HARD-REQUIRES jq: there is deliberately no `command -v jq` preflight and no
# degraded path. That is load-bearing. A helper that fail-softs would be dropped
# by the hop ON PURPOSE - the hop asks "can the SCRIPT do its job without this
# binary?" - which is the #831 residual the gate's own header documents as a
# remaining, accepted blindness. A control written against that residual would
# fail against main while looking like a demonstration.
set -euo pipefail
printf '{"ok":true}' | jq -r '.ok'
