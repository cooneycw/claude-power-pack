#!/usr/bin/env bash
# CONSTRUCTED ANCHOR for controls/lane-serveability-check (issue #1281). NOT A GATE.
#
# The check /qwen:auto and /gemma:auto actually ran BEFORE #895, re-expressed in
# lane-serveability-check.sh's contract so the harness can score it:
#
#     GET /api/version   is the daemon answering?
#     GET /api/tags      is the model in the catalogue?
#
# Both passing was read as "the lane can run". #895 measured why that is blind:
# registration (a manifest entry) is not serveability (weights loaded and
# producing a token). On 2026-09-13 both checks passed in ~13ms against a host
# whose loader was being SIGKILLed, and the run died ~18s later inside the
# delegated call. This anchor asks only those two questions, so it answers
# `serving` for every case whose /api/generate fails - which is every BAD case -
# and agrees with the gate on the one case where the model really serves.
set -uo pipefail
ENDPOINT=""; MODEL=""; LANE="unknown"; TIMEOUT=120
while [ $# -gt 0 ]; do
    case "$1" in
        --endpoint) ENDPOINT="$2"; shift 2 ;;
        --model)    MODEL="$2"; shift 2 ;;
        --lane)     LANE="$2"; shift 2 ;;
        --timeout)  TIMEOUT="$2"; shift 2 ;;
        --quiet)    shift ;;
        *)          echo "anchor: unknown argument $1" >&2; exit 2 ;;
    esac
done
ENDPOINT="${ENDPOINT%/}"
B=$(mktemp); trap 'rm -f "$B"' EXIT

emit() {
    echo "LANE_SERVE_LANE: $LANE"
    echo "LANE_SERVE_ENDPOINT: $ENDPOINT"
    echo "LANE_SERVE_MODEL: $MODEL"
    echo "LANE_SERVE_HTTP: $2"
    echo "LANE_SERVE_STATUS: $1"
}

code=$(curl -s -o "$B" -w '%{http_code}' --max-time "$TIMEOUT" "$ENDPOINT/api/version")
if [ "$code" != "200" ]; then emit unreachable "$code"; exit 3; fi
code=$(curl -s -o "$B" -w '%{http_code}' --max-time "$TIMEOUT" "$ENDPOINT/api/tags")
if [ "$code" != "200" ] || ! grep -qF "\"name\":\"$MODEL\"" "$B"; then emit dead "$code"; exit 1; fi
emit serving "$code"
exit 0
