#!/usr/bin/env sh
# Upgrade a global npm harness and report the VERSION TRANSITION (issue #1022).
#
# POSIX sh, no arrays, no bashisms: this runs from `/cpp:update` on a dev box and
# from `check-negative-controls.py` inside the uv/python3.11-bookworm-slim CI
# image, and it must give the same verdict in both.
#
#: NEGATIVE-CONTROL: controls/npm-global-upgrade
#
# WHY THIS EXISTS. `/cpp:update` Step 5d.2 used to run `npm install -g <pkg>`,
# read its exit code, and compose `Tier 6 refreshed`. On a host running node 20,
# `npm install -g @qwen-code/qwen-code` exits 0, prints no error, and installs
# THE VERSION THAT WAS ALREADY THERE: npm resolves `latest` down to the newest
# ENGINE-COMPATIBLE release, because 0.24.0 declares `engines.node >=22.0.0`.
# A real upgrade and a silently-capped one produced identical output, so a host
# sat nine minor versions behind while every update run reported it refreshed.
#
# THE VERDICT IS THE INSTALLED VERSION, NOT THE EXIT CODE. That is the whole
# change: an exit code says npm finished, and the question is whether the harness
# MOVED.
#
# CONTRACT
#   exit 0   upgraded      the installed version moved FORWARD
#            current       it did not move, and it already IS the published latest
#   exit 1   downgraded    the installed version moved BACKWARD
#            capped        it did not move, is behind latest, and latest's
#                          `engines.node` excludes this host's node
#            not-upgraded  it did not move, is behind latest, and NO engine
#                          constraint explains it
#            failed        the install command itself exited non-zero
#   exit 2   unknown       a version could not be read, so the transition is
#                          UNVERIFIED. This is not a pass. An offline host lands
#                          here, and that is correct: without the published
#                          version, `current` and `capped` are indistinguishable.
#
# THE CALLER MUST NOT TREAT A NON-ZERO EXIT AS FATAL. `capped` is a truthful
# report about a host, not a broken update run; `/cpp:update` reports it and
# carries on. What it must not do is compose an unqualified "refreshed" over it.
#
# NO ENGINE REASON IS INVENTED. `capped` requires an evaluable constraint
# (`>=<major>`) that this host's node actually fails. A constraint in any other
# shape (`^22 || ^20`, a range expression) is reported VERBATIM and labelled not
# evaluated, and the verdict stays `not-upgraded`. A plausible-sounding reason
# attached to a verdict nobody re-derives is worse than no reason: it ends the
# investigation.
#
# REVERSAL TRIGGER (issue #936, two-sided changes). This makes a report stricter,
# so the pressure later is to relax it the first time `unknown` is noisy on an
# offline box. What would justify moving it back is evidence that `unknown` fires
# on hosts that are ONLINE and healthy - i.e. that `npm view` is an unreliable
# reader rather than the host being genuinely unreadable. Noise alone is not that
# evidence, and neither is a run where the network was down: that verdict is
# correct. Anyone relaxing this should say which of the four verdicts they are
# willing to have become indistinguishable from the others again.
set -u

. "$(dirname "$0")/gate-lib.sh"

gate_map upgraded=0 downgraded=1 unknown=2 error=3

PACKAGE=""
BINARY=""
LABEL=""
NPM_CMD="npm"
NODE_CMD="node"
USE_SUDO=0
RUN_INSTALL=1

usage() {
    sed -n '2,50p' "$0"
    exit 0
}

# THE SHARED GATE MODULE (issue #1127, 3 of 4). Adopts `gate_map` and
# `gate_arg_value`; NOT `gate_emit` - this gate's `verdict()` prints
# `NPM_UPGRADE: <verdict> <detail>`, which its control keys on and which is not
# the module's `KEY: verdict - detail` shape.
#
# ONLY THE FIVE VALUE-TAKING FLAGS MOVE. `--sudo` and `--skip-install` take no
# value and stay exactly as they are: `gate_arg_value` answers "was a value
# supplied", and a boolean flag has none to supply. Converting them would be
# the over-application worth avoiding - a module adopted past the question it
# answers.
#
# WHAT THE USAGE EXIT WAS. `${2:?...}` exits 1 under bash, and 1 is THIS
# gate's `downgraded` code - so a dangling `--package` reported as "the
# installed version moved BACKWARD", a real and alarming verdict, on any host
# whose /bin/sh is bash. No verdict code moves: 0/1/2/3 unchanged.
while [ $# -gt 0 ]; do
    case "$1" in
        --package) gate_arg_value "$1" "$#" "${2-}"; PACKAGE=$GATE_VALUE; shift 2 ;;
        --binary) gate_arg_value "$1" "$#" "${2-}"; BINARY=$GATE_VALUE; shift 2 ;;
        --label) gate_arg_value "$1" "$#" "${2-}"; LABEL=$GATE_VALUE; shift 2 ;;
        --npm) gate_arg_value "$1" "$#" "${2-}"; NPM_CMD=$GATE_VALUE; shift 2 ;;
        --node) gate_arg_value "$1" "$#" "${2-}"; NODE_CMD=$GATE_VALUE; shift 2 ;;
        --sudo) USE_SUDO=1; shift ;;
        --skip-install) RUN_INSTALL=0; shift ;;
        -h|--help) usage ;;
        *) echo "npm-global-upgrade: unknown argument: $1" >&2; exit 2 ;;
    esac
done

[ -n "$PACKAGE" ] || { echo "npm-global-upgrade: --package is required" >&2; exit 2; }
[ -n "$BINARY" ] || { echo "npm-global-upgrade: --binary is required" >&2; exit 2; }
[ -n "$LABEL" ] || LABEL="$PACKAGE"

# A verdict line is printed on EVERY path, including the refusals above this
# point being the only exception - those are usage errors, not verdicts.
verdict() {
    echo "NPM_UPGRADE: $1"
}

# The first dotted-numeric token in the output, taken from the FRONT. `head -1`
# on a greedy sed would take the LAST match on the line instead, which on a
# harness that prints `qwen-code 0.15.10 (node v20.20.2)` reports node's version
# as the harness's - a wrong number that looks exactly like a right one.
extract_version() {
    printf '%s\n' "$1" \
        | grep -oE '[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?' \
        | head -1
}

harness_version() {
    out=$("$BINARY" --version 2>/dev/null) || return 1
    v=$(extract_version "$out")
    [ -n "$v" ] || return 1
    printf '%s' "$v"
}

# One numeric component of a version, with an ABSENT component as the empty
# string. Missing components are 0 to the caller, and a prerelease or build
# suffix is dropped WHOLE.
#
# NOT `cut -d. -f<n>`, which was the first cut and is wrong in two ways that a
# second reader reproduced and the author did not. `cut` prints the ENTIRE line
# when it contains no delimiter, so `>=22` parsed as 22.22.22 and condemned a
# node 22 host; and `tr -cd '0-9'` strips a suffix's letters while KEEPING its
# digits, so `1.5.0-rc1` parsed as patch 01 and `1.5.0-rc1 -> 1.5.0` read as a
# downgrade. The comment here used to claim the suffix was dropped. It was not:
# a comment asserting a property the code does not have is worse than the defect,
# because it is what the next reader checks instead of the code.
version_field() {
    _v="${1%%-*}"
    _v="${_v%%+*}"
    case "$2" in
        1) _f="${_v%%.*}" ;;
        2) _r="${_v#*.}"; [ "$_r" = "$_v" ] && _f="" || _f="${_r%%.*}" ;;
        3) _r="${_v#*.}"
           if [ "$_r" = "$_v" ]; then _f=""
           else _r2="${_r#*.}"; [ "$_r2" = "$_r" ] && _f="" || _f="${_r2%%.*}"; fi ;;
        *) _f="" ;;
    esac
    printf '%s' "$_f" | tr -cd '0-9'
}

version_lt() {
    i=1
    while [ "$i" -le 3 ]; do
        a=$(version_field "$1" "$i"); [ -n "$a" ] || a=0
        b=$(version_field "$2" "$i"); [ -n "$b" ] || b=0
        [ "$a" -lt "$b" ] && return 0
        [ "$a" -gt "$b" ] && return 1
        i=$((i + 1))
    done
    return 1
}

# `npm view` writes warnings to stderr and the value to stdout; an absent field
# prints nothing and still exits 0, so emptiness is checked, not assumed.
npm_view() {
    out=$("$NPM_CMD" view "$1" "$2" 2>/dev/null) || return 1
    out=$(printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | head -1 | tr -d "'\"" )
    [ -n "$out" ] || return 1
    printf '%s' "$out"
}

echo "NPM_UPGRADE_LABEL: $LABEL"
echo "NPM_UPGRADE_PACKAGE: $PACKAGE"

if ! command -v "$BINARY" >/dev/null 2>&1; then
    echo "NPM_UPGRADE_BEFORE: -"
    verdict "unknown $PACKAGE (harness '$BINARY' is not on PATH; nothing was installed or verified)"
    exit 2
fi

BEFORE=$(harness_version || true)
[ -n "$BEFORE" ] || BEFORE=""
echo "NPM_UPGRADE_BEFORE: ${BEFORE:--}"

INSTALL_EXIT=0
if [ "$RUN_INSTALL" -eq 1 ]; then
    if [ "$USE_SUDO" -eq 1 ]; then
        sudo -n "$NPM_CMD" install -g "$PACKAGE" || INSTALL_EXIT=$?
    else
        "$NPM_CMD" install -g "$PACKAGE" || INSTALL_EXIT=$?
    fi
    echo "NPM_UPGRADE_INSTALL_EXIT: $INSTALL_EXIT"
else
    echo "NPM_UPGRADE_INSTALL_EXIT: skipped"
fi

AFTER=$(harness_version || true)
[ -n "$AFTER" ] || AFTER=""
echo "NPM_UPGRADE_AFTER: ${AFTER:--}"

LATEST=$(npm_view "$PACKAGE" version || true)
[ -n "$LATEST" ] || LATEST=""
echo "NPM_UPGRADE_LATEST: ${LATEST:--}"

ENGINE=$(npm_view "${PACKAGE}@latest" engines.node || true)
[ -n "$ENGINE" ] || ENGINE=""
echo "NPM_UPGRADE_ENGINE: ${ENGINE:--}"

NODE_VER=$("$NODE_CMD" --version 2>/dev/null || true)
echo "NPM_UPGRADE_NODE: ${NODE_VER:--}"

# ---------------------------------------------------------------------------
# Verdict. Order matters: a failed install is reported as a failed install even
# when the version happens to satisfy something, because the next run's operator
# needs to know the command did not complete.
# ---------------------------------------------------------------------------
if [ "$INSTALL_EXIT" -ne 0 ]; then
    verdict "failed $PACKAGE (install exited $INSTALL_EXIT; still at ${BEFORE:-unreadable})"
    exit 1
fi

if [ -z "$AFTER" ]; then
    verdict "unknown $PACKAGE (the installed version could not be read after the install)"
    exit 2
fi

if [ -n "$BEFORE" ] && [ "$AFTER" != "$BEFORE" ]; then
    # A MOVE IS NOT AN UPGRADE. `after != before` was the whole test here, so an
    # install that replaced 1.6.0 with 1.5.0 - a dist-tag moved backward, or a
    # prerelease replaced by an older stable - reported `upgraded` and exit 0.
    # That is this issue's own defect class in the fix for it: a verdict that
    # cannot tell forward from backward, read by a summary nobody re-derives.
    if version_lt "$AFTER" "$BEFORE"; then
        verdict "downgraded $PACKAGE $BEFORE -> $AFTER (the install moved the harness BACKWARD)"
        exit 1
    fi
    if version_lt "$BEFORE" "$AFTER"; then
        verdict "upgraded $PACKAGE $BEFORE -> $AFTER"
        exit 0
    fi
    # The strings differ and the numeric cores do not: a prerelease or build
    # suffix changed. This helper does not implement semver prerelease ordering,
    # so the DIRECTION is not established - and an unestablished direction must
    # not fall through to `upgraded`, which is how `1.5.0 -> 1.5.0-beta.1` scored
    # as a successful upgrade before a second reader tried it.
    verdict "unknown $PACKAGE $BEFORE -> $AFTER (the change is confined to a prerelease or build suffix; direction NOT established)"
    exit 2
fi

if [ -z "$LATEST" ]; then
    verdict "unknown $PACKAGE $AFTER (the published version could not be read, so this upgrade is UNVERIFIED)"
    exit 2
fi

if [ "$AFTER" = "$LATEST" ]; then
    verdict "current $PACKAGE $AFTER (already the published latest)"
    exit 0
fi

# Behind latest and it did not move. Is there an engine constraint that ACTUALLY
# explains it on this host, or is the reason unknown?
NODE_NUM=""
case "$NODE_VER" in
    v[0-9]*) NODE_NUM="${NODE_VER#v}" ;;
    [0-9]*) NODE_NUM="$NODE_VER" ;;
esac

# THE CONSTRAINT IS EVALUATED WHOLE OR NOT AT ALL. Matching a `>=` PREFIX and
# reading only the major number is wrong in both directions, and both were
# reproduced: `>=22.0.0 || >=20.0.0` on node 20 read as capped although the
# second branch admits it, and `>=22.12.0` on node v22.1.0 read as "no engine
# constraint explains it" although it does. So the remainder after `>=` must be
# a bare dotted-numeric version - anything else (a disjunction, a caret, a
# range, a space) is UNEVALUATED - and the comparison is on the full triple.
REQ_VER=""
case "$ENGINE" in
    '>='*) REQ_VER="${ENGINE#>=}" ;;
esac
case "$REQ_VER" in
    ''|*[!0-9.]*) REQ_VER="" ;;
esac

if [ -n "$REQ_VER" ] && [ -n "$NODE_NUM" ] && version_lt "$NODE_NUM" "$REQ_VER"; then
    verdict "capped $PACKAGE $AFTER (latest $LATEST requires node $ENGINE; this host has $NODE_VER)"
    exit 1
fi

if [ -n "$ENGINE" ] && [ -z "$REQ_VER" ]; then
    verdict "not-upgraded $PACKAGE $AFTER (latest $LATEST; engines.node '$ENGINE' was NOT evaluated, so it does not explain this)"
    exit 1
fi

verdict "not-upgraded $PACKAGE $AFTER (latest $LATEST; no engine constraint explains it)"
exit 1
