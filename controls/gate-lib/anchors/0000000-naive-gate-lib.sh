#!/usr/bin/env sh
# THE BLIND ARTIFACT - the module as it would have been written WITHOUT its
# refusals, vendored so that "this control can fail" is demonstrated on every
# run rather than asserted once (ADR 0008, issue #924).
#
#: GATE-LIB-SENTINEL
#
# SYNTHETIC, kind=synthetic, sha 0000000. There is no historical commit: this
# module has no pre-fix version, because #1061's constraint 1 requires the
# control to land BEFORE any caller. What is refuted here is therefore a DESIGN
# rather than a commit - the "substitute a sensible default" shape that every
# one of the five hand-written idioms in `scripts/` was written to avoid, and
# that #1061's constraint 2 names as the thing a shared module would deliver to
# 15 gates at once.
#
# THE `--check` RUNNER BELOW IS BYTE-EQUIVALENT TO THE CURRENT GATE'S. Only the
# four library functions differ, so a verdict difference between this file and
# `scripts/gate-lib.sh` isolates the refusals and nothing else. Change the
# runner in one and this anchor stops demonstrating the property it exists for.
#
# WHAT IT DOES INSTEAD OF REFUSING, one line each:
#   gate_map        accepts any pairs, including a second verdict at 0
#   gate_arg_value  takes the candidate as given; a missing value becomes ""
#   gate_emit       prints whatever verdict it is handed
#   gate_exit       falls through to the good exit on an unmapped verdict
#
# Every one of those looks reasonable in isolation. Together they make a module
# that cannot report the other answer, which is what the register must catch.

GATE_USAGE_EXIT=64
GATE_MAP=""
GATE_VALUE=""

_gate_code_for() {
    case "$GATE_MAP" in
        *" $1="*) ;;
        *) return 1 ;;
    esac
    _gate_tail=${GATE_MAP#* "$1"=}
    printf '%s' "${_gate_tail%% *}"
}

gate_map() {
    GATE_MAP=" "
    for _gate_pair in "$@"; do
        GATE_MAP="$GATE_MAP$_gate_pair "
    done
}

gate_arg_value() {
    GATE_VALUE=$3
}

gate_emit() {
    _gate_key=$1
    _gate_verdict=$2
    shift 2
    if [ -n "$*" ]; then
        printf '%s: %s - %s\n' "$_gate_key" "$_gate_verdict" "$*"
    else
        printf '%s: %s\n' "$_gate_key" "$_gate_verdict"
    fi
}

gate_exit() {
    if _gate_exit_code=$(_gate_code_for "$1"); then
        exit "$_gate_exit_code"
    fi
    exit 0
}

_gate_self_invoked() {
    [ -r "$0" ] || return 1
    while IFS= read -r _gate_probe_line; do
        case "$_gate_probe_line" in
            '#: GATE-LIB-SENTINEL') return 0 ;;
        esac
    done < "$0"
    return 1
}

_gate_check_say() {
    # $1 verdict, $2 code, $3 detail
    if [ "$2" -eq 0 ]; then
        printf 'GATE_LIB: %s - %s\n' "$1" "$3"
    else
        printf 'GATE_LIB: %s - %s\n' "$1" "$3" >&2
    fi
    exit "$2"
}

_gate_check() {
    [ -n "${1:-}" ] || _gate_check_say unknown 2 "--check needs a case directory"
    [ -d "$1" ] || _gate_check_say unknown 2 "case directory '$1' is not a directory"

    _gate_probe="$1/probe.sh"
    [ -r "$_gate_probe" ] || _gate_check_say unknown 2 "no readable probe.sh under '$1'"

    # The probe is run under BOTH shells because measurement 3 above is a
    # divergence a single-shell run cannot see. bash's absence is a fact about
    # the MACHINE, not about the case - it is the same for every case, which is
    # what keeps this from being a per-case excuse (#1117).
    command -v bash >/dev/null 2>&1 || _gate_check_say unknown 2 \
        "bash is not installed, so the two-shell comparison could not be made"

    _gate_out_sh=$(GATE_LIB="$0" sh "$_gate_probe" 2>&1)
    _gate_rc_sh=$?
    _gate_out_bash=$(GATE_LIB="$0" bash "$_gate_probe" 2>&1)
    _gate_rc_bash=$?

    if [ "$_gate_rc_sh" -ne "$_gate_rc_bash" ]; then
        _gate_check_say unknown 2 \
            "sh exited $_gate_rc_sh and bash exited $_gate_rc_bash on one file and one input; a gate whose answer depends on its host shell has not answered"
    fi

    if [ "$_gate_rc_sh" -eq 0 ]; then
        _gate_check_say ok 0 "the probe completed under sh and bash (exit 0 in both)"
    fi

    # A CRASH IS NOT A REFUSAL - the #946 lesson, applied inside the instrument
    # written for it. A probe that falls over also exits non-zero, so a non-zero
    # exit counts as a refusal only when the module SAID so.
    #
    # BOTH OUTPUTS ARE READ, and the first cut read only sh's. Matching exit
    # codes are not matching causes: a probe that refuses under sh and dies
    # silently under bash with the same code was reported "refused identically",
    # so the control counted a crash as a detection - this control's own defect
    # class, one level up, found by the #1126 counter-model review.
    _gate_saw_sh=0
    _gate_saw_bash=0
    case "$_gate_out_sh" in *"gate-lib: refused - "*) _gate_saw_sh=1 ;; esac
    case "$_gate_out_bash" in *"gate-lib: refused - "*) _gate_saw_bash=1 ;; esac

    if [ "$_gate_saw_sh" -eq 0 ] && [ "$_gate_saw_bash" -eq 0 ]; then
        _gate_check_say unknown 2 \
            "the probe exited $_gate_rc_sh under both shells and printed no gate-lib refusal; that is a crash, not a refusal"
    fi
    if [ "$_gate_saw_sh" -ne "$_gate_saw_bash" ]; then
        _gate_check_say unknown 2 \
            "both shells exited $_gate_rc_sh but only one printed a gate-lib refusal (sh=$_gate_saw_sh bash=$_gate_saw_bash); equal exit codes are not equal causes"
    fi

    _gate_check_say refused 1 \
        "the module refused identically under sh and bash (exit $_gate_rc_sh)"
}

_gate_main() {
    case "${1:-}" in
        --check) shift; _gate_check "${1:-}" ;;
        -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
        *) _gate_check_say unknown 2 "usage: sh $0 --check <case-dir>" ;;
    esac
}

if _gate_self_invoked; then
    # THE EXIT LINE GOES INSIDE THIS BRANCH, and that placement is the whole
    # design (#1031 applied to a file that is both a library and a program).
    # `trap ... EXIT` installs into the CURRENT shell, and when this file is
    # SOURCED that shell belongs to the caller - flow-finish-gate.sh, which
    # installs its own `FLOW_FINISH_GATE_EXIT=` trap at line 137 and then
    # sources this file at line 200. A top-level trap here would silently
    # REPLACE it, deleting the one line the gate's caller reads to tell a
    # refusal from a pipe. That is the #1031 chainer hazard arriving from the
    # one direction the CHAINERS list cannot see, because the offending trap
    # would not be in the gate's own file at all.
    #
    # Self-invocation is decided by the sentinel at line 4, not by $0's name:
    # when sourced, $0 is the CALLER's path and the sentinel is absent, so this
    # branch does not run and the caller's trap stands untouched.
    #: DETECTION IS NOT AVAILABLE, SO DO NOT CLOBBER (#1061 counter-model
    #: re-review, MEDIUM). The comment above claimed the sentinel makes a
    #: sourced run unable to reach here. That is WRONG for one case, and the
    #: reviewer reproduced it:
    #:
    #:     bash -c 'trap "echo CALLER_EXIT >&2" EXIT; . "$0"; exit 7' ./scripts/gate-lib.sh
    #:
    #: entered this branch, REPLACED the caller's EXIT trap and exited 2 instead
    #: of 7. Measured afterwards: in that case bash exposes NOTHING that
    #: separates it from direct execution - $0, ${#BASH_SOURCE[@]}, BASH_SOURCE[0]
    #: and BASH_SOURCE[1] are all identical to a real `bash gate-lib.sh` run. The
    #: state is undecidable from in here, so a better detector is not available
    #: and pretending otherwise is how the first fix failed.
    #:
    #: The remedy is therefore to make the answer NOT MATTER: install the marker
    #: only when nobody else's EXIT trap is there to destroy. `trap -p` is bash
    #: (dash resets traps inside command substitution and always reports none),
    #: which is sufficient - the hazard is a bash one, and
    #: flow-finish-gate.sh, the caller this protects, is a bash script.
    _gate_existing_exit_trap=""
    if [ -n "${BASH_VERSION:-}" ]; then
        # shellcheck disable=SC3044
        _gate_existing_exit_trap="$(trap -p EXIT 2>/dev/null)"
    fi
    if [ -z "$_gate_existing_exit_trap" ]; then
        trap 'printf "GATE_LIB_EXIT=%d\n" "$?" >&2' EXIT
    fi
    _gate_main "$@"
fi
