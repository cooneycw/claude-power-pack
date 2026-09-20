#!/usr/bin/env bash
# flow-driver-retirement-check.sh - Is it safe to DELETE a lifecycle driver
# command? (issue #1017, executing the trigger #934 committed.)
#
#: NEGATIVE-CONTROL: controls/flow-driver-retirement-check
#
# CONTRACT
#   exit 0  RETIREMENT: clear   - no live and no undetermined role drives on it
#   exit 1  RETIREMENT: blocked - at least one LIVE role drives on it
#   exit 3  RETIREMENT: unknown - the question could not be answered
#
# THREE OUTCOMES, NEVER TWO, and `unknown` is not `clear`. Deleting a driver
# command removes the lifecycle instructions any session running on it is in the
# middle of executing - #934 called that "not a merge conflict; it is three
# in-flight PRs losing their driver mid-run". So this authorises a destructive,
# unrecoverable-for-the-victim action and nothing downstream re-derives it.
#
# WHY THIS IS A SCRIPT AND NOT THE PARAGRAPH OF SHELL IT REPLACES.
# #934 committed the procedure as prose beside the command it governed, and
# #1017 asked for it to be RUN. Running it surfaced the reason prose was not
# enough: its first guard is
#
#     raw=$(flow-wave-registry.sh list --wave "$W" --json) || { unknown; }
#
# and `list` EXITS 0 WITH AN EMPTY ROSTER when the registry does not exist -
# verified 2026-09-16 against FLOW_WAVE_REGISTRY_DIR=/nonexistent, which printed
# only the `merge_starvation` metadata block and `FLOW_WAVE: listed`, exit 0. So
# the branch that exists to say "I could not look" was UNREACHABLE, and a host
# with no registry at all read `RETIREMENT: clear` - the precise "no output,
# therefore nobody is there" collapse the prose spends three paragraphs warning
# against. THE REGISTRY FILE IS THEREFORE READ DIRECTLY, and its absence or
# unparseability is `unknown`. (`controls/.../cases/bad-registry-absent` is that
# case, committed, because re-reading the procedure only ever showed what it
# MEANT.)
#
# TWO WAYS TO GET THIS WRONG, IN OPPOSITE DIRECTIONS AT ONCE:
#
#   - an unreadable registry, or an absent helper, produces no matching output.
#     That is UNKNOWN. Counting it as absence authorises deleting the command
#     out from under a session still running on it.
#   - `list` renders RELEASED and STALE roles with their drivers too, so a
#     substring scan counts sessions that ended months ago and blocks the
#     retirement forever. In the `cpp-completion` wave, `worker-A` is exactly
#     that: `liveness: released`, `driver: flow:auto_codex`.
#
# LIVENESS IS A FOUR-VALUE VOCABULARY - live, released, stale, unknown - and
# only the middle two are conclusively inactive. `unknown` means the registry
# could not determine whether the process exists; it is not evidence of absence.
#
# WAVES ARE ENUMERATED, NOT SUPPLIED. The registry helper has no verb that lists
# waves, so the committed procedure was per-wave by construction and left "a
# wave nobody thought to check" as a standing hole in a gate whose whole subject
# is the difference between looking and finding nothing. The wave set is derived
# from the registry's own top-level keys - the same object `list` reads - so the
# denominator cannot silently exclude a wave. `--wave` still narrows it for a
# caller who wants one.
#
# USAGE
#   flow-driver-retirement-check.sh --driver flow:auto_codex
#   flow-driver-retirement-check.sh --driver flow:auto_codex --wave cpp-completion
#   flow-driver-retirement-check.sh --driver X --registry-dir <dir>   # controls
set -u

# THE SHARED GATE MODULE (issue #1127, 4 of 4). Adopts `gate_map` and
# `gate_arg_value`; NOT `gate_emit` - `unknown()` and the tail print
# `RETIREMENT: <verdict> ...`, which this gate's control keys on and which is
# not the module's `KEY: verdict - detail` shape.
#
# THIS IS THE ONE WHERE IT MATTERED MOST. `${2:?...}` exits 1 under bash, and 1
# is THIS gate's `blocked` code - so a dangling `--driver` reported as "at least
# one LIVE role drives on it", the verdict that REFUSES a retirement. A usage
# error rendering as the safe-side answer is the worst direction for it to be
# wrong in, because nobody investigates a refusal that agrees with caution: the
# operator sees "blocked", does not delete, and never learns the gate never ran.
# The module's usage exit is outside every verdict this gate declares.
#
# The comment below about usage and unknown SHARING exit 3 is now history for
# the usage half, and is left in place because it explains why the `unknown`
# verdict still exits 3. Usage errors no longer land there.
. "$(dirname "$0")/gate-lib.sh"

gate_map clear=0 blocked=1 unknown=3

DRIVER=""
ONE_WAVE=""
REG_DIR="${FLOW_WAVE_REGISTRY_DIR:-}"
HELPER="${FLOW_WAVE_REGISTRY_BIN:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --driver)       gate_arg_value "$1" "$#" "${2-}"; DRIVER=$GATE_VALUE; shift 2 ;;
        --wave)         gate_arg_value "$1" "$#" "${2-}"; ONE_WAVE=$GATE_VALUE; shift 2 ;;
        --registry-dir) gate_arg_value "$1" "$#" "${2-}"; REG_DIR=$GATE_VALUE; shift 2 ;;
        --helper)       gate_arg_value "$1" "$#" "${2-}"; HELPER=$GATE_VALUE; shift 2 ;;
        -h|--help)      sed -n '2,61p' "$0"; exit 0 ;;
        *) echo "flow-driver-retirement-check: unknown argument: $1" >&2; exit 3 ;;
    esac
done

# An unknown VERDICT and a usage error are different facts, but both exit 3:
# neither answered the question, and a caller that deletes on anything but 0 is
# already wrong. The marker line says which.
unknown() {
    echo "RETIREMENT: unknown - $1"
    exit 3
}

[ -n "$DRIVER" ] || unknown "no --driver was given, so nothing was examined"

command -v jq >/dev/null 2>&1 || unknown "jq is not installed, so no roster could be parsed"

# --- resolve the registry helper ---------------------------------------------
# Same order as every other flow helper (#581/#590), with the in-tree sibling
# last so this runs from a checkout and in CI. ABSENCE IS UNKNOWN: a helper that
# is not installed produces no matching roles, which is indistinguishable from a
# clear wave and is the first of the two wrong directions above.
if [ -z "$HELPER" ]; then
    for cand in \
        "$HOME/.claude/scripts/flow-wave-registry.sh" \
        "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/scripts/flow-wave-registry.sh" \
        "$(dirname -- "$0")/flow-wave-registry.sh"
    do
        [ -f "$cand" ] || continue
        HELPER="$cand"
        break
    done
fi
if [ -z "$HELPER" ] || [ ! -f "$HELPER" ]; then
    unknown "flow-wave-registry.sh could not be resolved, so no wave could be read"
fi

# --- resolve the registry FILE ------------------------------------------------
# Resolved the way the helper resolves it, then READ, because the helper's own
# exit status cannot distinguish "empty" from "absent" (see the header).
if [ -z "$REG_DIR" ]; then
    REG_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/cc-flow-wave"
fi
REG_FILE="$REG_DIR/registry.json"

[ -f "$REG_FILE" ] || \
    unknown "the registry '$REG_FILE' does not exist, so no wave could be enumerated"
[ -r "$REG_FILE" ] || \
    unknown "the registry '$REG_FILE' is not readable, so no wave could be enumerated"
jq -e 'type == "object"' "$REG_FILE" >/dev/null 2>&1 || \
    unknown "the registry '$REG_FILE' did not parse as a JSON object"

# --- enumerate the waves ------------------------------------------------------
if [ -n "$ONE_WAVE" ]; then
    # A NAME THE REGISTRY DOES NOT CARRY IS `unknown`, NOT AN EMPTY WAVE.
    # `list --wave <typo>` returns an empty roster and exits 0, so `--wave` with
    # a misspelt name used to produce `waves=1 matched=0` and a CLEAR verdict -
    # recreating, through the narrowing flag, the exact empty-population failure
    # this gate exists to prevent. Narrowing to a wave that EXISTS stays
    # legitimate; retirement across every wave uses the unrestricted form.
    jq -e --arg w "$ONE_WAVE" 'has($w)' "$REG_FILE" >/dev/null 2>&1 || \
        unknown "wave '$ONE_WAVE' is not in '$REG_FILE', so nothing was examined"
    WAVES="$ONE_WAVE"
else
    WAVES="$(jq -r 'keys[]' "$REG_FILE" 2>/dev/null)" || \
        unknown "the registry's wave keys could not be enumerated"
fi

# A registry that parses but holds no wave is not a clear verdict either: there
# is no population to have looked at, and this gate's subject is exactly that
# distinction.
[ -n "$WAVES" ] || \
    unknown "the registry '$REG_FILE' contains no wave, so nothing was examined"

# --- classify, per wave -------------------------------------------------------
TOTAL_LIVE=0
TOTAL_UNDET=0        # ROLES whose liveness is not one of the terminal states
TOTAL_UNREADABLE=0   # WAVES that could not be listed or parsed at all
TOTAL_MATCHED=0
WAVES_SEEN=0
BLOCKED_WAVES=""
UNKNOWN_WAVES=""

while IFS= read -r WAVE; do
    [ -n "$WAVE" ] || continue
    WAVES_SEEN=$((WAVES_SEEN + 1))

    # The status is tested on the assignment itself: a separate `[ $? -ne 0 ]`
    # reads whatever ran last, which in an earlier draft of this loop was the
    # `echo` from the previous iteration.
    if ! raw="$(FLOW_WAVE_REGISTRY_DIR="$REG_DIR" bash "$HELPER" list --wave "$WAVE" --json 2>/dev/null)" \
       || [ -z "$raw" ]; then
        UNKNOWN_WAVES="$UNKNOWN_WAVES $WAVE(unlistable)"
        TOTAL_UNREADABLE=$((TOTAL_UNREADABLE + 1))
        continue
    fi

    # The JSON is an object keyed by ROLE NAME followed by FLOW_WAVE_* contract
    # lines that are not part of it. Alongside the roles sit METADATA keys -
    # `wave_policy` (#699), `unregistered_claims` (#687) and `merge_starvation`,
    # and the middle one is an ARRAY. A filter that drops only `wave_policy`
    # then asks an array for `.liveness`, the whole query dies, and the check
    # reports `unknown` on a roster that was perfectly readable: a wrong answer
    # in the safe direction, which is still wrong and never resolves. So the
    # named keys are dropped AND anything that is not an object is dropped -
    # belt and braces, because the metadata key set is not ours to freeze.
    # `set -o pipefail` for this pipeline ONLY: jq can print a complete `[]` for
    # a valid JSON prefix and THEN die on trailing garbage, so a non-empty
    # stdout is not evidence that the parse succeeded. Testing emptiness alone
    # accepted that partial result and reported the wave clear.
    roster="$(set -o pipefail; printf '%s' "$raw" | sed '/^FLOW_WAVE/,$d' | jq -c --arg d "$DRIVER" '
        to_entries
        | map(select(.key | IN("wave_policy", "unregistered_claims", "merge_starvation") | not))
        | map(.value)
        | map(select(type == "object"))
        | map(select(.driver == $d))' 2>/dev/null)" || roster=""
    # And EXACTLY ONE array, checked with `jq -s` rather than by counting lines.
    # Command substitution strips the TRAILING newline, so two emitted arrays
    # carry only one newline between them and a `wc -l > 1` test passes; bare
    # `jq -e 'type == "array"'` then reports the status of the LAST value in the
    # stream, so both arrays were accepted. The counts below came back multiline,
    # the arithmetic died, and the run printed `RETIREMENT: clear` and exited 0
    # with a LIVE role in the first value - a clearance strictly worse than the
    # blindness the surrounding check was added to remove. Slurp mode is the
    # honest test: one value, and that value an array.
    if [ -z "$roster" ] \
       || ! printf '%s' "$roster" | jq -se 'length == 1 and (.[0] | type == "array")' >/dev/null 2>&1; then
        UNKNOWN_WAVES="$UNKNOWN_WAVES $WAVE(unparseable)"
        TOTAL_UNREADABLE=$((TOTAL_UNREADABLE + 1))
        continue
    fi

    # ONLY `released` AND `stale` ESTABLISH INACTIVITY, and everything that is
    # neither those nor `live` is UNDETERMINED - a missing `liveness` key, a
    # null, or a value this gate has never heard of. Counting `unknown` by name
    # and letting the remainder fall through to "inactive" is the same
    # not-pending-therefore-done shape the header warns about, one level in: a
    # helper that renames a state, or a roster whose entries predate the field,
    # would have authorised the deletion. The done-set is required, not the
    # absence of the blocking one.
    matched="$(printf '%s' "$roster" | jq -r 'length')"
    live="$(printf '%s'    "$roster" | jq -r '[ .[] | select(.liveness == "live") ] | length')"
    inactive="$(printf '%s' "$roster" | jq -r '[ .[] | select(.liveness == "released" or .liveness == "stale") ] | length')"
    # THE SLURP CHECK ABOVE IS WHAT MAKES THIS ARITHMETIC SAFE, and it is the
    # only thing that needs to. `jq -r 'length'` over exactly one array always
    # yields one integer, so a second "is this a number" guard here would be
    # code no input can reach - written, reviewed, and unable to report the
    # other verdict. One was written, and removed once no input could be named
    # that fires it: an unreachable guard is indistinguishable from a working
    # one, which is this repository's own subject.
    undet=$((matched - live - inactive))

    TOTAL_MATCHED=$((TOTAL_MATCHED + matched))
    TOTAL_LIVE=$((TOTAL_LIVE + live))
    TOTAL_UNDET=$((TOTAL_UNDET + undet))

    [ "$live"  = "0" ] || BLOCKED_WAVES="$BLOCKED_WAVES $WAVE($live live)"
    [ "$undet" = "0" ] || UNKNOWN_WAVES="$UNKNOWN_WAVES $WAVE($undet undetermined)"

    echo "RETIREMENT_WAVE: $WAVE matched=$matched live=$live inactive=$inactive unknown=$undet"
done <<EOF
$WAVES
EOF

# The denominator, always, per #952: a zero that cannot show where it looked
# reads UNKNOWN. `matched` is the load-bearing half - it is the positive control
# on the extraction, and a 0 here on a registry known to carry this driver means
# the query is blind rather than the waves clear.
echo "RETIREMENT_SCOPE: driver=$DRIVER waves=$WAVES_SEEN matched=$TOTAL_MATCHED registry=$REG_FILE"

if [ "$TOTAL_LIVE" != "0" ]; then
    echo "RETIREMENT: blocked ($TOTAL_LIVE live role(s) on '$DRIVER' in:$BLOCKED_WAVES)"
    exit 1
fi
if [ "$TOTAL_UNDET" != "0" ] || [ "$TOTAL_UNREADABLE" != "0" ]; then
    echo "RETIREMENT: unknown ($TOTAL_UNDET role(s) of undetermined liveness on '$DRIVER'," \
         "$TOTAL_UNREADABLE wave(s) unreadable, in:$UNKNOWN_WAVES)"
    exit 3
fi
echo "RETIREMENT: clear for '$DRIVER' across $WAVES_SEEN wave(s)"
exit 0
