#!/usr/bin/env bash
# lane-serveability-check.sh - Can this local-model lane actually SERVE? (issue #895)
#
# Problem:
#   `/qwen:auto` and `/gemma:auto` each gate delegation on two questions:
#
#     GET /api/version   is the daemon answering?
#     GET /api/tags      is the model in the catalogue?
#
#   Neither asks whether the model can be LOADED. Registration (a manifest
#   entry) and serveability (weights resident and producing a token) are
#   different facts, and the qwen serving host sat exactly between them on
#   2026-09-13: both checks passed in ~13ms, the run proceeded, and it died
#   ~18s later inside the delegated call with
#
#     HTTP 500  {"error":"llama-server process has terminated: signal: killed"}
#
#   - an error naming an internal process rather than a lane. `/gemma:auto`
#   carries the identical gate and therefore the identical latent defect; it
#   had simply not fired, because that host was healthy.
#
#   This helper is the discriminating probe: one single-token generation,
#   which is the only check that separates "registered" from "serveable".
#
# Usage:
#   lane-serveability-check.sh --endpoint URL --model NAME
#                              [--lane qwen|gemma] [--timeout SECONDS] [--quiet]
#
#   --endpoint  Ollama base URL, e.g. http://127.0.0.1:11434. REQUIRED.
#   --model     The model to probe, e.g. qwen3.8-code:latest. REQUIRED.
#               Probing a DIFFERENT model than the lane will run proves nothing
#               about the lane, so the caller passes the lane's own model.
#   --lane      Which lane is asking. Advisory: it is reported and tunes
#               nothing. An unnamed lane is probed identically.
#   --timeout   Ceiling in seconds (default 120). See "Why 120s" below - this
#               is a hung-socket backstop, NOT the discriminator.
#   --quiet     Contract lines only; suppress the human-readable summary.
#
# Output ends with a machine-readable contract:
#   LANE_SERVE_LANE:     qwen | gemma | unknown
#   LANE_SERVE_ENDPOINT: <url as given>
#   LANE_SERVE_MODEL:    <model as given>
#   LANE_SERVE_HTTP:     <status code, or 000 when no response arrived>
#   LANE_SERVE_ELAPSED:  <seconds, as curl measured them>
#   LANE_SERVE_DETAIL:   <the server's own error text; omitted when there is none>
#   LANE_SERVE_STATUS:   serving | dead | unreachable | unknown
#
# LANE, ENDPOINT, MODEL, HTTP, ELAPSED and STATUS are always emitted. DETAIL is
# omitted when there is nothing to say, following the convention
# `delegated-run-check.sh` established for the same reason: a DETAIL line that
# is always present teaches readers to ignore it.
#
# Exit codes:
#   0  serving      - the model produced a token
#   1  dead         - the server answered and CANNOT serve this model
#   2  usage error
#   3  unreachable  - no usable response arrived (connection refused/dropped,
#                     timeout, DNS). The lane cannot be used either way, but
#                     the reason is transport, not the model
#   4  unknown      - the probe could not be PERFORMED (no curl). Distinct from
#                     every verdict above; see "Why unknown exists" below
#
# ---------------------------------------------------------------------------
# One failure, THREE shapes - why this helper cannot key on any single one
# ---------------------------------------------------------------------------
# The load-time kill does not surface consistently. Six probes at
# /api/generate against the broken qwen host on 2026-09-13, same request bytes
# each time:
#
#   HTTP 500 in 17.4s / 18.2s / 18.6s   body carries the server's own words,
#                                       {"error":"llama-server process has
#                                        terminated: signal: killed"}
#   HTTP 000 in 16.5s / 17.1s           curl exit 52, connection closed with
#                                       an EMPTY body - no diagnosis at all
#   HTTP 000 in 0.008s                  curl exit 56, reset immediately, when
#                                       it lands right after a prior failure
#
# Two consequences, and both are load-bearing.
#
# First, a probe that recognised only the 500 would report a healthy verdict -
# or a bare transport error - on a third of the samples. So the helper treats
# an absent response as its own verdict (`unreachable`, exit 3) rather than as
# noise, and BOTH callers are instructed to refuse delegation on either. The
# sub-second reset is the trap inside the trap: it looks like a network blip
# and is the same dead loader, which is why the shapes are enumerated here.
#
# Second, this refutes the tidier story that /v1 loses the diagnosis while
# /api/generate keeps it. Two /v1 samples both dropped the connection, which
# looked like an endpoint property until /api/generate produced the same drop.
# The shape is NOT determined by the endpoint. /api/generate is probed anyway,
# for reasons that survive the correction: it is ollama's native endpoint
# regardless of which transport a harness happens to use, it is what
# `/qwen:status` already probes, and the error text was observed there and
# never on /v1 - a weak preference on small samples, stated as one.
#
# What this check does NOT cover is tool calling. A model can serve a token and
# still drop tool calls, which is the ollama `/v1` defect (ollama/ollama#14958)
# that bites once a system prompt passes ~1,600 tokens. That question is
# answered by `/gemma:status`'s tool-calling pre-flight, which runs a real
# harness invocation past the threshold. Widening this probe toward it would
# make the preflight slow without making it conclusive.
#
# ---------------------------------------------------------------------------
# Why 120s, and why the timeout is NOT the discriminator
# ---------------------------------------------------------------------------
# Issue #895 warned that a probe which times out on a healthy-but-cold lane
# converts this bug into its mirror image. Measurements taken while building
# this, across both hosts:
#
#   healthy, model GPU-resident          0.067 - 0.085s   (4 runs)
#   healthy, model cold (reload)         7.0s, 12.2s
#   healthy, 7.18 GB spilled to CPU      18.5 - 67.3s     (6 runs)
#   BROKEN, loader SIGKILLed             17.4 - 18.6s     (HTTP 500)
#
# Read the last two rows together: a degraded-but-working lane and a dead lane
# overlap completely in the time domain. No deadline separates them, in either
# direction - a 30s ceiling would condemn a lane that is merely spilled, and no
# ceiling at all would still catch the dead one, because the dead one ANSWERS.
#
# So the discriminator is the RESPONSE, never the clock. 120s is chosen as a
# backstop against a socket that hangs forever: comfortably past the slowest
# healthy observation (67.3s), and irrelevant on the failure path, which never
# reached it in any sample - the broken host answers or drops within ~18s. On a
# healthy warm lane the probe costs ~70-90ms, so the ceiling is not a latency
# tax; it is an upper bound healthy runs never approach.
#
# The spilled-to-CPU row is worth keeping in view when tempted to lower it.
# That lane was serving real work at 18-67s per token, slowly and correctly. A
# ceiling tuned to "fail fast" would have declared it dead and blocked a lane
# that was merely degraded, which is the mirror-image bug #895 named in advance.
#
# ---------------------------------------------------------------------------
# Why `unknown` exists (detector contract, docs/agents/detector-contracts.md)
# ---------------------------------------------------------------------------
# Question 1, the membership floor: this check's success message must not claim
# more than its input population supports. `serving` is asserted only after a
# 2xx response whose body carries a generated-response field and no error
# field - a positive observation over a population of exactly one probe, which
# is what the message says. The state this detector must be able to REPRESENT,
# and could not if it were written with two outcomes, is "the probe did not
# run": with no curl there is no observation, and reporting that as either
# `serving` or `dead` would be an assertion over an empty population. It is
# `unknown`, exit 4, and callers are told to treat it as unchecked - never as
# clean.
#
# Question 2, the ownership boundary: a non-zero here names the endpoint AND
# the model it was asked about, and DETAIL carries the server's own words about
# that model. A neighbouring lane on a different host cannot produce a verdict
# attributed to this one. The case worth separating explicitly is a model that
# is absent rather than unloadable - ollama answers that with its own 404 text,
# which lands in DETAIL, so `dead` never silently absorbs "you asked for the
# wrong name".

set -uo pipefail

ENDPOINT=""
MODEL=""
LANE="unknown"
TIMEOUT=120
QUIET=0

while [ $# -gt 0 ]; do
    case "$1" in
        --endpoint)
            ENDPOINT="${2:-}"; shift 2 || true ;;
        --model)
            MODEL="${2:-}"; shift 2 || true ;;
        --lane)
            LANE="${2:-}"; shift 2 || true ;;
        --timeout)
            TIMEOUT="${2:-}"; shift 2 || true ;;
        --quiet)
            QUIET=1; shift ;;
        --help|-h)
            sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)
            echo "lane-serveability-check: unknown argument: $1" >&2
            exit 2 ;;
    esac
done

if [ -z "$ENDPOINT" ] || [ -z "$MODEL" ]; then
    echo "lane-serveability-check: usage: lane-serveability-check.sh --endpoint URL --model NAME [--lane L] [--timeout S] [--quiet]" >&2
    exit 2
fi

case "$LANE" in
    qwen|gemma|unknown) ;;
    *)
        echo "lane-serveability-check: unknown lane '$LANE' (expected qwen|gemma)" >&2
        exit 2 ;;
esac

if ! printf '%s' "$TIMEOUT" | grep -Eq '^[0-9]+$' || [ "$TIMEOUT" -eq 0 ]; then
    echo "lane-serveability-check: --timeout must be a positive integer, got: $TIMEOUT" >&2
    exit 2
fi

# Trailing slashes would produce `//api/generate`, which ollama serves but which
# makes the reported endpoint disagree with the one probed.
ENDPOINT="${ENDPOINT%/}"

emit() {
    # $1 status, $2 http, $3 elapsed, $4 detail (may be empty)
    echo "LANE_SERVE_LANE: $LANE"
    echo "LANE_SERVE_ENDPOINT: $ENDPOINT"
    echo "LANE_SERVE_MODEL: $MODEL"
    echo "LANE_SERVE_HTTP: $2"
    echo "LANE_SERVE_ELAPSED: $3"
    [ -n "$4" ] && echo "LANE_SERVE_DETAIL: $4"
    echo "LANE_SERVE_STATUS: $1"
}

# --- The unperformable case -------------------------------------------------
# No curl means no observation. This is reported as its own state rather than
# folded into a verdict, so a caller cannot read "we could not look" as "we
# looked and it was fine".
if ! command -v curl >/dev/null 2>&1; then
    [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: curl is not installed - the probe could NOT be performed. This is unchecked, not clean."
    emit "unknown" "-" "-" "curl not installed"
    exit 4
fi

# --- The probe --------------------------------------------------------------
# A single token is all that is needed: the failure being detected happens
# during weight load, long before generation, so asking for more output buys no
# additional discrimination and only costs time.
#
# `"think": false` is the native hard switch for thinking-enabled models (both
# lane defaults are). Without it a thinking model can spend its one permitted
# token inside a reasoning block and return an empty response field, which is a
# healthy lane that this check would have to call ambiguous.
#
# `keep_alive` is deliberately NOT sent. A request-level value overrides the
# server's own policy, and the gemma host runs OLLAMA_KEEP_ALIVE=-1 to pin a
# 19 GB model in VRAM permanently - a probe that shipped "5m" would quietly
# un-pin it and hand the next real run a cold load. A preflight reports on the
# server; it does not reconfigure it. Omitting the field inherits whatever the
# operator configured, which is the only correct answer here.
REQUEST=$(printf '{"model":%s,"prompt":"hi","stream":false,"think":false,"options":{"num_predict":1}}' \
    "$(printf '%s' "$MODEL" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || printf '"%s"' "$MODEL")")

BODY_FILE=$(mktemp -t lane-serve-XXXXXX.json)
trap 'rm -f "$BODY_FILE"' EXIT

# -s so progress noise stays out of the contract; deliberately NOT -f, which
# would discard the 500 body - and that body is the entire diagnosis.
METRICS=$(curl -s -o "$BODY_FILE" -w '%{http_code} %{time_total}' \
    --max-time "$TIMEOUT" \
    -H 'Content-Type: application/json' \
    "$ENDPOINT/api/generate" -d "$REQUEST" 2>/dev/null)
CURL_EXIT=$?

HTTP="${METRICS%% *}"
ELAPSED="${METRICS##* }"
[ -n "$HTTP" ] || HTTP="000"
[ -n "$ELAPSED" ] && [ "$ELAPSED" != "$HTTP" ] || ELAPSED="-"

# The server's own words, when it managed to say any. Parsed with python3 when
# available (ollama's error text contains characters a shell pattern would
# mangle) and with a sed fallback when it is not, because a helper whose
# diagnosis depends on an optional interpreter is a helper that goes quiet on
# the hosts least likely to have one.
extract_error() {
    if command -v python3 >/dev/null 2>&1; then
        python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as fh:
        payload = json.load(fh)
except Exception:
    sys.exit(0)
if isinstance(payload, dict):
    err = payload.get("error")
    if isinstance(err, dict):
        err = err.get("message")
    if err:
        print(str(err)[:300])
' "$1" 2>/dev/null
    else
        sed -n 's/.*"error"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$1" 2>/dev/null | head -1 | cut -c1-300
    fi
}

served() {
    # A 2xx alone is not serveability: ollama returns 200 with an `error` field
    # in some paths, and an empty body is not a generated token either. Require
    # the positive artifact - a `response` field - and the absence of an error.
    if command -v python3 >/dev/null 2>&1; then
        python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as fh:
        payload = json.load(fh)
except Exception:
    sys.exit(1)
if not isinstance(payload, dict) or payload.get("error"):
    sys.exit(1)
sys.exit(0 if "response" in payload else 1)
' "$1" 2>/dev/null
    else
        grep -q '"response"' "$1" 2>/dev/null && ! grep -q '"error"' "$1" 2>/dev/null
    fi
}

DETAIL=$(extract_error "$BODY_FILE")

# --- Verdict ----------------------------------------------------------------
if [ "$CURL_EXIT" -ne 0 ] || [ "$HTTP" = "000" ]; then
    # No usable response: refused, dropped mid-flight, timed out, DNS. curl 28
    # is the timeout; everything else is a transport fault. The lane is
    # unusable either way, but saying WHICH matters - a dropped connection on a
    # host whose /api/version answers is the `/v1`-shaped failure above, and a
    # timeout at the ceiling is a different conversation from a refusal.
    case "$CURL_EXIT" in
        28) WHY="no response within ${TIMEOUT}s" ;;
        7)  WHY="connection refused" ;;
        6)  WHY="could not resolve host" ;;
        52) WHY="server closed the connection without a reply" ;;
        56) WHY="connection reset while receiving" ;;
        *)  WHY="no usable response (curl exit $CURL_EXIT)" ;;
    esac
    [ -n "$DETAIL" ] || DETAIL="$WHY"
    if [ "$QUIET" -eq 0 ]; then
        echo "lane-serveability-check: the ${LANE} lane is UNREACHABLE at $ENDPOINT - $WHY."
        echo "  The model server did not return a usable answer for '$MODEL', so the lane cannot run."
    fi
    emit "unreachable" "$HTTP" "$ELAPSED" "$DETAIL"
    exit 3
fi

if [ "$HTTP" -ge 200 ] 2>/dev/null && [ "$HTTP" -lt 300 ] 2>/dev/null && served "$BODY_FILE"; then
    if [ "$QUIET" -eq 0 ]; then
        echo "lane-serveability-check: the ${LANE} lane SERVED a token from '$MODEL' at $ENDPOINT in ${ELAPSED}s."
        echo "  One generation succeeded; this says nothing about tool-calling or sustained throughput."
    fi
    emit "serving" "$HTTP" "$ELAPSED" ""
    exit 0
fi

# The server answered and cannot serve. This is the registered-but-not-
# serveable state the whole helper exists for.
[ -n "$DETAIL" ] || DETAIL="HTTP $HTTP with no generated response and no error text"
if [ "$QUIET" -eq 0 ]; then
    echo "lane-serveability-check: the ${LANE} lane is DOWN - '$MODEL' is registered at $ENDPOINT but cannot be served."
    echo "  The server answered in ${ELAPSED}s and said: $DETAIL"
    echo "  Do NOT delegate to this lane: the model server is reachable and the model is in its"
    echo "  catalogue, but loading it fails. A 'signal: killed' here is the loader being reaped by"
    echo "  the host (memory ceiling), which is a host-side fix, not a setting in this repo."
fi
emit "dead" "$HTTP" "$ELAPSED" "$DETAIL"
exit 1
