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
#   Probe mode - take an observation:
#     lane-serveability-check.sh --endpoint URL --model NAME
#                                [--lane qwen|gemma] [--timeout SECONDS]
#                                [--valid-for SECONDS] [--quiet]
#
#   Age mode - is an observation ALREADY TAKEN still current? Probes nothing:
#     lane-serveability-check.sh --check-age EPOCH --recorded STATUS
#                                [--valid-for SECONDS] [--lane qwen|gemma]
#                                [--quiet]
#
#   --endpoint  Ollama base URL, e.g. http://127.0.0.1:11434. REQUIRED in probe
#               mode; ignored in age mode, which probes nothing.
#   --model     The model to probe, e.g. qwen3.8-code:latest. REQUIRED in probe
#               mode; ignored in age mode.
#               Probing a DIFFERENT model than the lane will run proves nothing
#               about the lane, so the caller passes the lane's own model.
#   --lane      Which lane is asking. Advisory: it is reported and tunes
#               nothing. An unnamed lane is probed identically.
#   --timeout   Ceiling in seconds (default 120). See "Why 120s" below - this
#               is a hung-socket backstop, NOT the discriminator.
#   --valid-for How long a probe result may be READ AS CURRENT, in seconds
#               (default 120). See "Why 120s for the validity window" below.
#               In probe mode it only sets the emitted LANE_SERVE_VALID_FOR; it
#               changes no verdict. In age mode it is the bound being applied.
#   --check-age The LANE_SERVE_AT value from an earlier probe. Switches to age
#               mode: no request is made and no serveability verdict is formed.
#   --recorded  The LANE_SERVE_STATUS that earlier probe reported. REQUIRED in
#               age mode - see "Why the age answer needs the verdict" below.
#   --quiet     Contract lines only; suppress the human-readable summary.
#
# Output ends with a machine-readable contract:
#   LANE_SERVE_LANE:     qwen | gemma | unknown
#   LANE_SERVE_ENDPOINT: <url as given>
#   LANE_SERVE_MODEL:    <model as given>
#   LANE_SERVE_HTTP:     <status code, or 000 when no response arrived>
#   LANE_SERVE_ELAPSED:  <seconds, as curl measured them>
#   LANE_SERVE_AT:       <epoch seconds when the observation was taken, or -
#                         when this host has no `date`>
#   LANE_SERVE_VALID_FOR: <seconds this result may be read as current>
#   LANE_SERVE_DETAIL:   <the server's own error text; omitted when there is none>
#   LANE_SERVE_STATUS:   serving | dead | unreachable | unknown
#
# LANE, ENDPOINT, MODEL, HTTP, ELAPSED, AT, VALID_FOR and STATUS are always
# emitted in probe mode. DETAIL is omitted when there is nothing to say,
# following the convention `delegated-run-check.sh` established for the same
# reason: a DETAIL line that is always present teaches readers to ignore it.
#
# Age mode emits a DIFFERENT block, and deliberately emits NO LANE_SERVE_STATUS:
#   LANE_SERVE_LANE:      <as given>
#   LANE_SERVE_AT:        <the --check-age value, echoed>
#   LANE_SERVE_AGE:       <seconds since that observation, or - when undecidable>
#   LANE_SERVE_VALID_FOR: <the window applied>
#   LANE_SERVE_RECORDED:  <the --recorded verdict, echoed>
#   LANE_SERVE_DETAIL:    <why, when the answer is not a plain `fresh`>
#   LANE_SERVE_FRESHNESS: fresh | stale | unknown
#
# Exit codes (probe mode):
#   0  serving      - the model produced a token
#   1  dead         - the server answered and CANNOT serve this model
#   2  usage error
#   3  unreachable  - no usable response arrived (connection refused/dropped,
#                     timeout, DNS). The lane cannot be used either way, but
#                     the reason is transport, not the model
#   4  unknown      - the probe could not be PERFORMED (no curl). Distinct from
#                     every verdict above; see "Why unknown exists" below
#
# Exit codes (age mode). A FRESH recording exits exactly as that recording did;
# anything else is exit 4, because the honest answer is "re-probe":
#   0  the recorded `serving` is still current
#   1  the recorded `dead` is still current
#   2  usage error
#   3  the recorded `unreachable` is still current
#   4  the recording is STALE, or its age is UNDECIDABLE, or the recorded
#      verdict was itself `unknown`. All three mean: this says nothing, probe
#      again. They are separated in DETAIL, never in the exit code
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
# Why the age answer needs the verdict, and why `fresh` is not a STATUS
# ---------------------------------------------------------------------------
# `serving|dead|unreachable|unknown` all answer ONE question: can this lane
# serve? Freshness answers a different one: is my answer still current? They are
# orthogonal - a recorded verdict can be fresh AND dead - so they live in
# separate variables. Putting `fresh` into LANE_SERVE_STATUS would make one
# variable carry two questions, which is the precise mechanism by which a caller
# reads one and believes the other.
#
# Age mode therefore emits NO LANE_SERVE_STATUS at all. It takes no observation,
# so it has no serveability verdict to report, and a caller reading only that
# variable gets nothing rather than something it can misread as a pass. This is
# the same refusal as `unknown` for the no-curl case, applied once more: a mode
# that observes nothing must not emit anything readable as go.
#
# `--recorded` is REQUIRED for the same reason, structurally. It is not possible
# to ask this script "is my answer still current?" without telling it which
# answer, so it is not possible to get a go out of it without having the verdict
# in hand. `LANE_SERVE_FRESHNESS: fresh` beside `LANE_SERVE_RECORDED: dead`
# exits 1, not 0 - freshness never launders a verdict.
#
# Two kinds of bad input, deliberately given two different exits:
#   --recorded outside serving|dead|unreachable|unknown is exit 2. That set is
#   this script's OWN output; a value outside it means the caller is not reading
#   this script, which is a wiring error.
#   --check-age that is not an epoch is exit 4, NOT exit 2. That value is DATA -
#   a caller extracts it from a cached probe result, and an extraction that
#   comes back empty or garbled is a runtime condition whose correct handling is
#   "re-probe", not "abort the preflight".
#
# ---------------------------------------------------------------------------
# Why 120s for the validity window
# ---------------------------------------------------------------------------
# 120s IS A POLICY CHOICE BOUNDED BY ONE MEASUREMENT, NOT A DERIVED VALUE.
#
# The evidence is the six probes of one host recorded above. The closest
# healthy-to-broken transition observed there was on the order of minutes. That
# supports "the window must be well under minutes" and supports nothing finer.
# It is one host, one day, one failure mode; it is NOT a general property of
# ollama, and the next host may transition faster.
#
# So this number is pre-committed on both sides, because a threshold with only
# one named direction of travel gets moved by whoever finds it inconvenient:
#
#   SHORTEN it on evidence of faster transitions - any observation of a lane
#   going from serving to dead inside the current window.
#   LENGTHEN it only on evidence that transitions are genuinely slower than
#   minutes, gathered across more than one host.
#
#   NOT a reason to lengthen it: that UNKNOWN is inconvenient on long runs.
#
# That last line is the one that matters. A 30-minute run against a 120s window
# spends most of itself UNKNOWN, and that is the finding rather than a defect: a
# preflight cannot vouch for a long run, and the window is what makes it admit
# that instead of implying otherwise. The answer to that pressure is a re-probe
# trigger, which this change deliberately does not decide - not a wider window,
# which would hide the gap rather than close it.
#
# The window bounds how long a pass may be READ AS CURRENT. It does not schedule
# anything and does not probe. When to re-probe stays the caller's decision, and
# issue #921 leaves it open on purpose.
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

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "LANE_SERVE_EXIT=%d\n" "$?" >&2' EXIT

ENDPOINT=""
MODEL=""
LANE="unknown"
TIMEOUT=120
QUIET=0
VALID_FOR=120
CHECK_AGE=""
AGE_MODE=0
RECORDED=""

# A value-taking flag given as the LAST argument used to hang the script.
# `shift 2` fails when only one argument remains, `|| true` swallowed that
# failure without consuming anything, and the loop spun on the same argument
# forever. Every value-taking flag was affected, including the four that predate
# the freshness work. A missing value is a usage error, not a hang.
require_value() {
    # $1 flag, $2 the caller's argument count at the point of the call
    if [ "$2" -lt 2 ]; then
        echo "lane-serveability-check: $(flatten "$1") requires a value" >&2
        exit 2
    fi
}

# `printf ... | grep -Eq '^[0-9]+$'` tests a LINE, not the whole argument, so a
# multiline value whose first line happened to be digits passed validation. It
# then reached `[ ... -gt ... ]` as a multiline string, the comparison errored,
# the guard fell through, and the value was echoed into the contract - which let
# a second line be INJECTED into the output block. `case` matches the entire
# string, so an embedded newline lands in `*[!0-9]*` and is rejected.
#
# The digit cap is load-bearing, not decoration. Bash arithmetic is 64-bit and
# WRAPS, so a long enough digit string yields a small, plausible and wrong
# result rather than an error. 11 digits reaches the year 5138, which is past
# any timestamp this helper will ever be handed.
# Every user-supplied value that reaches OUTPUT goes through this first. A
# newline inside an echoed value can otherwise begin a line that a caller reads
# as part of the contract - including a verdict line the helper never emitted.
# Applied at the point of output rather than to the values themselves, so what
# is probed is unchanged and only what is REPORTED is made safe to parse.
flatten() {
    printf '%s' "$1" | tr '\n\r' '  ' | cut -c1-80
}

is_bounded_decimal() {
    # $1 value, $2 maximum digits
    case "$1" in
        ""|*[!0-9]*) return 1 ;;
    esac
    [ "${#1}" -le "$2" ]
}

while [ $# -gt 0 ]; do
    case "$1" in
        --endpoint)
            require_value "$1" $#; ENDPOINT="$2"; shift 2 ;;
        --model)
            require_value "$1" $#; MODEL="$2"; shift 2 ;;
        --lane)
            require_value "$1" $#; LANE="$2"; shift 2 ;;
        --timeout)
            require_value "$1" $#; TIMEOUT="$2"; shift 2 ;;
        --valid-for)
            require_value "$1" $#; VALID_FOR="$2"; shift 2 ;;
        --check-age)
            require_value "$1" $#; CHECK_AGE="$2"; AGE_MODE=1; shift 2 ;;
        --recorded)
            require_value "$1" $#; RECORDED="$2"; shift 2 ;;
        --quiet)
            QUIET=1; shift ;;
        --help|-h)
            # Print the header down to the first divider rather than a fixed
            # line range: the usage block grows, and a stale `sed -n '2,40p'`
            # silently truncates the help instead of failing.
            sed -n '2,/^# ---------/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)
            echo "lane-serveability-check: unknown argument: $(flatten "$1")" >&2
            exit 2 ;;
    esac
done

if [ "$AGE_MODE" -eq 0 ] && { [ -z "$ENDPOINT" ] || [ -z "$MODEL" ]; }; then
    echo "lane-serveability-check: usage: lane-serveability-check.sh --endpoint URL --model NAME [--lane L] [--timeout S] [--valid-for S] [--quiet]" >&2
    echo "lane-serveability-check:        lane-serveability-check.sh --check-age EPOCH --recorded STATUS [--valid-for S] [--lane L] [--quiet]" >&2
    exit 2
fi

case "$LANE" in
    qwen|gemma|unknown) ;;
    *)
        echo "lane-serveability-check: unknown lane '$(flatten "$LANE")' (expected qwen|gemma)" >&2
        exit 2 ;;
esac

if ! is_bounded_decimal "$TIMEOUT" 9 || [ "$((10#$TIMEOUT))" -eq 0 ]; then
    echo "lane-serveability-check: --timeout must be a positive integer, got: $(flatten "$TIMEOUT")" >&2
    exit 2
fi
# Normalised so a leading zero cannot reach arithmetic as an octal literal, and
# so the value echoed into the contract is the one actually applied.
TIMEOUT=$((10#$TIMEOUT))

if ! is_bounded_decimal "$VALID_FOR" 9 || [ "$((10#$VALID_FOR))" -eq 0 ]; then
    echo "lane-serveability-check: --valid-for must be a positive integer, got: $(flatten "$VALID_FOR")" >&2
    exit 2
fi
VALID_FOR=$((10#$VALID_FOR))

# The closed set is this script's own output, so a value outside it is wiring,
# not data. Absent and unrecognised are the same error and get the same exit.
if [ "$AGE_MODE" -eq 1 ]; then
    case "$RECORDED" in
        serving|dead|unreachable|unknown) ;;
        "")
            echo "lane-serveability-check: --check-age requires --recorded STATUS (serving|dead|unreachable|unknown)." >&2
            echo "  Freshness alone is not a verdict: an age says whether an answer is current, never what that answer was." >&2
            exit 2 ;;
        *)
            echo "lane-serveability-check: --recorded must be one of serving|dead|unreachable|unknown, got: $(flatten "$RECORDED")" >&2
            exit 2 ;;
    esac
fi

# Trailing slashes would produce `//api/generate`, which ollama serves but which
# makes the reported endpoint disagree with the one probed.
ENDPOINT="${ENDPOINT%/}"

# The moment the observation was taken. A host without `date` reports `-`
# rather than an empty value or a fabricated zero: an unknown time must read as
# unknown, and `-` is what age mode then correctly refuses to age.
now_epoch() {
    date +%s 2>/dev/null || printf '%s' '-'
}

emit() {
    # $1 status, $2 http, $3 elapsed, $4 detail (may be empty)
    echo "LANE_SERVE_LANE: $LANE"
    echo "LANE_SERVE_ENDPOINT: $(flatten "$ENDPOINT")"
    echo "LANE_SERVE_MODEL: $(flatten "$MODEL")"
    echo "LANE_SERVE_HTTP: $2"
    echo "LANE_SERVE_ELAPSED: $3"
    echo "LANE_SERVE_AT: $(now_epoch)"
    echo "LANE_SERVE_VALID_FOR: $VALID_FOR"
    [ -n "$4" ] && echo "LANE_SERVE_DETAIL: $4"
    echo "LANE_SERVE_STATUS: $1"
}

emit_age() {
    # $1 freshness, $2 age, $3 detail (may be empty). Deliberately NO
    # LANE_SERVE_STATUS: this mode took no observation, so it has no
    # serveability verdict, and must emit nothing a caller can read as one.
    echo "LANE_SERVE_LANE: $LANE"
    echo "LANE_SERVE_AT: $CHECK_AGE"
    echo "LANE_SERVE_AGE: $2"
    echo "LANE_SERVE_VALID_FOR: $VALID_FOR"
    echo "LANE_SERVE_RECORDED: $RECORDED"
    [ -n "$3" ] && echo "LANE_SERVE_DETAIL: $3"
    echo "LANE_SERVE_FRESHNESS: $1"
}

# --- Age mode: is an observation ALREADY TAKEN still current? ---------------
# No request is made. The window bounds how long a recorded answer may be read
# as current; it does not decide when to re-probe, which is the caller's call.
if [ "$AGE_MODE" -eq 1 ]; then
    NOW=$(now_epoch)

    # This value is DATA - a caller extracts it from a cached probe result - and
    # it is echoed back into the contract block, so a garbled cache carrying a
    # newline could otherwise FORGE the verdict this mode exists to withhold.
    # A value with a newline in it is not an epoch either way, so this costs no
    # legitimate input.
    CHECK_AGE=$(flatten "$CHECK_AGE")

    # Bounded, not merely digit-shaped. `08` used to pass this check and then
    # blow up inside `$(( ))` as an invalid octal literal - which did not stop
    # age mode, it fell out of it and ran the PROBE, emitting the
    # `LANE_SERVE_STATUS` this mode must never produce. A digit string longer
    # than an epoch would instead wrap 64-bit arithmetic into a small, plausible
    # and wrong age.
    if ! is_bounded_decimal "$CHECK_AGE" 11; then
        [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: the recorded timestamp is not readable, so its age is UNKNOWN - probe again rather than trusting it."
        emit_age "unknown" "-" "recorded timestamp is not an epoch: '${CHECK_AGE}'"
        exit 4
    fi

    if [ "$NOW" = "-" ]; then
        [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: this host cannot read the clock, so the age is UNKNOWN - probe again rather than trusting it."
        emit_age "unknown" "-" "no clock available on this host to age the recording against"
        exit 4
    fi

    # `10#` forces base 10: without it a zero-padded timestamp is read as octal.
    AGE=$(( NOW - 10#$CHECK_AGE ))

    # A negative age means the writing clock and the reading clock disagree.
    # No tolerance is allowed, because every current caller writes and reads
    # this timestamp on the SAME host, where skew is an anomaly rather than NTP
    # jitter. A cross-host caller would make a tolerance a real question, and it
    # would need its own measurement before a number is picked - so if one ever
    # appears, this branch is where it must be answered rather than widened.
    if [ "$AGE" -lt 0 ]; then
        [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: the recorded timestamp is in the FUTURE, so the age is UNKNOWN - probe again rather than trusting it."
        emit_age "unknown" "$AGE" "recorded timestamp is $(( -AGE ))s in the future (clock skew)"
        exit 4
    fi

    # Inclusive: a recording exactly at the bound has not yet exceeded it.
    if [ "$AGE" -gt "$VALID_FOR" ]; then
        [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: the ${LANE} lane's recorded '${RECORDED}' is STALE (${AGE}s old, window ${VALID_FOR}s) - it says nothing now; probe again."
        emit_age "stale" "$AGE" "recorded ${AGE}s ago, beyond the ${VALID_FOR}s window"
        exit 4
    fi

    # Fresh. The exit code is the RECORDED verdict's own, never a bare pass:
    # freshness says the answer is current, not that the answer was yes.
    case "$RECORDED" in
        serving)
            [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: the ${LANE} lane's recorded 'serving' is ${AGE}s old, within the ${VALID_FOR}s window."
            emit_age "fresh" "$AGE" ""
            exit 0 ;;
        dead)
            [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: the ${LANE} lane's recorded 'dead' is still current (${AGE}s old). Do NOT delegate."
            emit_age "fresh" "$AGE" "the recorded verdict was 'dead'; being recent does not make it usable"
            exit 1 ;;
        unreachable)
            [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: the ${LANE} lane's recorded 'unreachable' is still current (${AGE}s old). Do NOT delegate."
            emit_age "fresh" "$AGE" "the recorded verdict was 'unreachable'; being recent does not make it usable"
            exit 3 ;;
        *)
            # `unknown` recorded: a recent NON-observation. Fresh and useless.
            [ "$QUIET" -eq 1 ] || echo "lane-serveability-check: the recorded verdict was 'unknown' - a recent non-observation is still unchecked, not clean."
            emit_age "fresh" "$AGE" "the recorded verdict was itself 'unknown'; there is nothing to keep fresh"
            exit 4 ;;
    esac
fi

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
# CHAINED, NOT REPLACED (issue #1031): a bare `trap ... EXIT` here would
# silently discard the LANE_SERVE_EXIT= line installed at the top of this file,
# and nothing would report its absence. $? is captured FIRST, before the
# cleanup runs, or the reported status becomes `rm`'s.
trap '_rc=$?; rm -f "$BODY_FILE"; printf "LANE_SERVE_EXIT=%d\n" "$_rc" >&2' EXIT

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
