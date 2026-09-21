#!/usr/bin/env sh
# gate-lib.sh - one home for the argument and verdict conventions (issue #1126).
#
#: GATE-LIB-SENTINEL
#: NEGATIVE-CONTROL: controls/gate-lib
#
# FIRST SLICE OF #1061. Nothing sources this yet, and that is deliberate: the
# module is a class-X instrument by ADR 0008's bound - its verdict is consumed
# by every gate that migrates onto it and re-derived by none - and constraint 2
# of #1061 says a SHARED FAIL-OPEN REACHES EVERY CALLER AT ONCE. So the control
# lands first, before anything depends on it, rather than as a follow-up.
#
# CONTRACT (sourced)
#   gate_map        <verdict>=<code>...   declare THIS gate's exit mapping
#   gate_arg_value  <flag> <argc> <cand>  parse one value-taking flag
#   gate_emit       <KEY> <verdict> [..]  the contract line
#   gate_exit       <verdict>             exit per the declared map
#
# CONTRACT (executed)
#   sh gate-lib.sh --check <case-dir>
#   exit 0  GATE_LIB: ok      - the case's probe completed under sh AND bash
#   exit 1  GATE_LIB: refused - the module refused, identically in both shells
#   exit 2  GATE_LIB: unknown - the shells disagreed, the probe died without a
#           refusal, or the comparison could not be made. NOT a pass.
#
# ---------------------------------------------------------------------------
# WHY THIS EXISTS - three measurements, not a preference (all on 778ad82)
# ---------------------------------------------------------------------------
# 1. ZERO SHELL SCRIPTS IN THIS REPOSITORY SOURCE A SIBLING. `grep -lE
#    '^\s*(source|\.) ' scripts/*.sh` returns nothing. 13 files carry `shift 2`
#    across 56 occurrences, and the rule "a value-taking flag given as the final
#    argument must not be silently empty" is written FIVE different ways:
#    `${2:?msg}`, `${2:-}` plus `|| die_usage`, `shift 2 || shift`, an explicit
#    `[ $# -ge 2 ]`, and a `require_value` helper. #992 was ONE defect found six
#    times and fixed six times; the shape is still copied.
#
# 2. THE EXIT MAPPING ALREADY DISAGREES. `shellcheck-gate.sh` and
#    `npm-global-upgrade.sh` use 2 for unknown; `flow-driver-retirement-check.sh`
#    uses 3 and records that its 3 doubles as a usage error. Consumers read those
#    numbers TODAY, so this module does NOT unify them - `gate_map` is per gate.
#    What moves in here is the INVARIANT the headers state in prose and nothing
#    enforces: no verdict but the good one may map to the good exit.
#
# 3. `${2:?}` - the guard #992 measured as "exit 1" - IS SHELL-DEPENDENT.
#       printf 'set -u\nV="${2:?needs a value}"\n' > p.sh
#       bash p.sh --flag  -> 1        dash p.sh --flag  -> 2
#    On the real gate, same file, same argument:
#       bash scripts/shellcheck-gate.sh --root  -> 1
#       sh   scripts/shellcheck-gate.sh --root  -> 2
#    That file declares `exit 1 = findings`, so under bash a USAGE ERROR REPORTS
#    AS A FINDING. Latent today - every live invocation supplies the value - and
#    it is why every refusal here exits a code this module CHOOSES rather than
#    inheriting whatever the host shell does with `:?`. It is also why `--check`
#    runs each probe under BOTH shells: a single-shell control cannot see it.
#
# ---------------------------------------------------------------------------
# WHY THIS FILE IS TOP-LEVEL AND NOT `scripts/lib/gate.sh`
# ---------------------------------------------------------------------------
# #1061 proposed `scripts/lib/`. Measured against a fixture tree holding
# `scripts/shellcheck-gate.sh` AND `scripts/lib/gate.sh`:
#
#   instrument-census-check.py  ->  INSTRUMENT_CENSUS_EXAMINED: 1
#   scripts-inventory-check.py  ->  SCRIPTS_INVENTORY_EXAMINED: 1, and exit ok
#
# Two shell files present, one examined, and the inventory gate reports OK.
# Both enumerate with `scripts_dir.iterdir()` filtered on `path.is_file()`, so a
# SUBDIRECTORY IS SKIPPED WHOLE. `check-negative-controls.py` is the third:
# its `DISCOVERY_SCOPE` constant states the same scope, explains that widening
# one reader without the other would split the numerator's population from the
# denominator's, and `tests/test_negative_controls.py` pins it - a marker in a
# `scripts/` subdirectory MUST NOT be discovered. Placing the wave's most
# load-bearing instrument under `scripts/lib/` would put it outside all three,
# silently. Top level is the only placement consistent with them.
#
# ---------------------------------------------------------------------------
# WHY A REFUSAL IS AN `exit`, NOT A RETURN CODE
# ---------------------------------------------------------------------------
# `gate_arg_value` SETS `GATE_VALUE` in the caller's shell instead of printing a
# value for `$( )` to capture. A command substitution runs in a SUBSHELL, so an
# `exit` inside one does not stop the caller - the refusal would be discarded by
# any caller who forgot `|| exit $?`, which is precisely the thing the five
# hand-written idioms depend on an author remembering. Sourced functions run in
# the caller's shell, so `exit` here really exits, and the refusal cannot be
# dropped.
#
# ---------------------------------------------------------------------------
# NOT `local`, ON PURPOSE
# ---------------------------------------------------------------------------
# `local` is not POSIX and `shellcheck -s sh` rejects it. `shellcheck-gate.sh`
# is `#!/usr/bin/env sh` and runs in `koalaman/shellcheck-alpine`, which has NO
# bash, so a bash-only module would work on a dev box and be unsourceable in the
# image where the first migration target actually runs. Every helper variable
# here therefore carries a `_gate_` prefix and is a global by necessity.

# The bootstrap refusal code, used before `gate_map` has run and as the default
# `usage` mapping afterwards. 64 is sysexits.h EX_USAGE: distinct from 0 (good),
# from 1 (a finding in every gate in this tree) and from 2 and 3 (the two codes
# already in use for "could not tell"). A migrating gate that must keep its
# current number declares `usage=N` in its own `gate_map`.
GATE_USAGE_EXIT=64

# The declared mapping, as a space-delimited string. POSIX sh has no associative
# array; the leading and trailing spaces are load-bearing, because membership is
# tested as `*" name="*` and a bare `*name=*` would match `ok=` when asked about
# `k`.
GATE_MAP=""

# Set by `gate_arg_value` on success. Never read unless that call returned.
GATE_VALUE=""

_gate_refuse() {
    printf 'gate-lib: refused - %s\n' "$1" >&2
    exit "$GATE_USAGE_EXIT"
}

_gate_require_map() {
    [ -n "$GATE_MAP" ] || _gate_refuse \
        "$1 was called before gate_map; a gate with no declared mapping has no good exit to protect, and guessing one is the fail-open this module exists to remove"
}

# The verdict grammar, in ONE place. `gate_map` validates what it DECLARES and
# `_gate_code_for` validates what it LOOKS UP, and until the counter-model review
# of #1126 only the first half existed. The map is a flat string, so an
# unvalidated lookup is a substring match: with ` finding=1 ok=0 usage=64 `
# declared, `gate_exit "finding=1 ok"` matched ` finding=1 ok=`, resolved to 0,
# AND EXITED 0 - an undeclared verdict reaching the good exit through the very
# function written to stop that. Measured before the fix, under sh and bash both.
_gate_valid_verdict() {
    case "$1" in
        [a-z]*) ;;
        *) return 1 ;;
    esac
    case "$1" in
        *[!a-z0-9-]*) return 1 ;;
    esac
    return 0
}

# Echo the code declared for a verdict; return 1 when it is not in the map.
# Callers MUST test the return value - a bare `$( )` yields an empty string on
# failure, and `[ "" -eq 0 ]` is a shell error, not a good exit.
_gate_code_for() {
    _gate_valid_verdict "$1" || return 1
    case "$GATE_MAP" in
        *" $1="*) ;;
        *) return 1 ;;
    esac
    _gate_tail=${GATE_MAP#* "$1"=}
    printf '%s' "${_gate_tail%% *}"
}

# ---------------------------------------------------------------------------
# gate_map <verdict>=<code> ...
# ---------------------------------------------------------------------------
# Declares THIS gate's vocabulary and its exit codes. The codes are the gate's
# own and are never normalised here (see measurement 2 above).
#
# THE ONE RULE IT ENFORCES: exactly one verdict maps to exit 0. That single
# constraint IS "an unknowable answer is never rendered as a clean one" (#1014,
# #800) expressed in exit codes, and it is DERIVED rather than a hardcoded list
# of unknown-ish words - a list would go stale the first time a gate invented a
# sixth name for the third state, which is the drift this whole wave is about.
#
# It deliberately does NOT force a consumer's policy. `flow-wave-mailbox.sh`
# records that its two consumers read `unknown` in opposite directions on
# purpose - the duplicate-arm guard treats it as 0 so a wave is never blocked by
# an unavailable guard, reporting treats it as `unknown` - and collapsing that
# would erase a distinction two incidents paid for (#814, #821). The mapping is
# per gate for exactly this reason.
gate_map() {
    [ $# -gt 0 ] || _gate_refuse "gate_map needs at least one <verdict>=<code> pair"

    GATE_MAP=" "
    _gate_good=""

    for _gate_pair in "$@"; do
        case "$_gate_pair" in
            *=*) ;;
            *) _gate_refuse "gate_map: '$_gate_pair' is not <verdict>=<code>" ;;
        esac

        _gate_name=${_gate_pair%%=*}
        _gate_code=${_gate_pair#*=}

        _gate_valid_verdict "$_gate_name" || _gate_refuse \
            "gate_map: verdict '$_gate_name' must begin with a lowercase letter and hold only lowercase letters, digits and '-'"
        case "$_gate_code" in
            ''|*[!0-9]*) _gate_refuse "gate_map: '$_gate_name' maps to '$_gate_code', which is not a non-negative integer" ;;
        esac
        # Above 125 a shell reinterprets the value (126/127 are its own "cannot
        # execute" answers and 128+n is "killed by signal n"), so a gate exiting
        # there reports something it did not say.
        [ "$_gate_code" -le 125 ] || _gate_refuse \
            "gate_map: '$_gate_name' maps to $_gate_code; codes above 125 are the shell's own, not a gate's"

        case "$GATE_MAP" in
            *" $_gate_name="*) _gate_refuse "gate_map: verdict '$_gate_name' is declared twice" ;;
        esac

        if [ "$_gate_code" -eq 0 ]; then
            if [ -n "$_gate_good" ]; then
                _gate_refuse \
                    "gate_map: '$_gate_good' and '$_gate_name' both map to the good exit 0; an answer that is not the good one must never be able to render as clean"
            fi
            if [ "$_gate_name" = usage ]; then
                _gate_refuse "gate_map: 'usage' may not map to the good exit 0; a usage error is never a pass"
            fi
            _gate_good=$_gate_name
        fi

        GATE_MAP="$GATE_MAP$_gate_name=$_gate_code "
    done

    if [ -z "$_gate_good" ]; then
        GATE_MAP=""
        _gate_refuse "gate_map: no verdict maps to the good exit 0; a gate that can never report success is not a gate"
    fi

    # `usage` is reserved and always reachable, so `gate_exit usage` works
    # whether or not the caller declared it. A gate that wants a different
    # number declares one; that declaration is validated by the loop above like
    # any other, including the 0 refusal.
    case "$GATE_MAP" in
        *" usage="*) GATE_USAGE_EXIT=$(_gate_code_for usage) ;;
        *) GATE_MAP="${GATE_MAP}usage=$GATE_USAGE_EXIT " ;;
    esac
}

# ---------------------------------------------------------------------------
# gate_arg_value <flag> <remaining-argc> <candidate>
# ---------------------------------------------------------------------------
# Typical caller:
#
#   while [ $# -gt 0 ]; do
#       case "$1" in
#           --root) gate_arg_value "$1" "$#" "${2-}"; ROOT=$GATE_VALUE; shift 2 ;;
#
# THE DECISION IS THE COUNT, NEVER THE EMPTINESS OF THE CANDIDATE. `--root ""`
# supplies an empty value and is accepted; `--root` at the end of the line
# supplies none and is refused. Deciding on `[ -n "$2" ]` instead - which two
# live idioms in this tree do - conflates the two and rejects a legitimate empty
# argument, so the count is what is passed in.
gate_arg_value() {
    _gate_require_map gate_arg_value
    [ $# -eq 3 ] || _gate_refuse \
        "gate_arg_value needs <flag> <remaining-argc> <candidate>; got $# argument(s)"

    case "$2" in
        ''|*[!0-9]*) _gate_refuse "gate_arg_value: remaining-argc '$2' is not a number; pass \"\$#\"" ;;
    esac

    [ "$2" -ge 2 ] || _gate_refuse "$1 needs a value, and it is the last argument"

    GATE_VALUE=$3
}

# ---------------------------------------------------------------------------
# gate_emit <KEY> <verdict> [detail ...]
# ---------------------------------------------------------------------------
# The contract line, formatted and validated in one place. A verdict outside the
# declared map is REFUSED rather than printed: a typo that reaches a consumer's
# grep is a verdict nobody declared, and the consumer reads its absence as the
# other answer.
#
# The good verdict goes to stdout and everything else to stderr, which is the
# convention already in `shellcheck-gate.sh` and what lets a pipeline separate a
# clean run from a reported one without parsing.
# A KNOWN, MEASURED NON-ADOPTER (issue #1061). `scripts/flow-finish-gate.sh` uses
# `gate_map`, `gate_exit` and `gate_arg_value` and deliberately does NOT use this
# function. That is not an unfinished migration and should not be "completed"
# without moving what depends on it first.
#
# It emits `FLOW_FINISH_GATE: <verdict> (<detail>)` on STDOUT. This function emits
# `KEY: verdict - detail` and routes any non-zero verdict to STDERR. Both
# differences are load-bearing there, measured against its six registered controls:
#
#   parenthesised detail required   3  declared-gates, plan-reconciliation, subsumption
#   end-anchored `^...: fail$`      2  derivation, flow-finish-gate  (ANY detail breaks these)
#   unanchored, survives            1  resume
#
# So adopting it there risks FIVE of six controls, plus 85 assertions in
# tests/test_flow_finish_gate.py that read the verdict from stdout. The safety
# property #1061 exists for - one verdict maps to 0, per-verdict exit codes, and an
# unmapped verdict refusing rather than falling through - lives entirely in the
# other three functions, which that gate does adopt. This one carries a line
# format.
gate_emit() {
    _gate_require_map gate_emit
    [ $# -ge 2 ] || _gate_refuse "gate_emit needs <KEY> <verdict> [detail ...]; got $# argument(s)"

    _gate_key=$1
    _gate_verdict=$2
    shift 2
    _gate_detail=$*

    case "$_gate_key" in
        [A-Za-z]*) ;;
        *) _gate_refuse "gate_emit: key '$_gate_key' must begin with a letter" ;;
    esac
    case "$_gate_key" in
        *[!A-Za-z0-9_-]*) _gate_refuse "gate_emit: key '$_gate_key' may hold only letters, digits, '_' and '-'" ;;
    esac

    if ! _gate_emit_code=$(_gate_code_for "$_gate_verdict"); then
        _gate_refuse "gate_emit: '$_gate_verdict' is not in the declared map ($GATE_MAP)"
    fi

    if [ -n "$_gate_detail" ]; then
        _gate_line="$_gate_key: $_gate_verdict - $_gate_detail"
    else
        _gate_line="$_gate_key: $_gate_verdict"
    fi

    if [ "$_gate_emit_code" -eq 0 ]; then
        printf '%s\n' "$_gate_line"
    else
        printf '%s\n' "$_gate_line" >&2
    fi
}

# ---------------------------------------------------------------------------
# gate_exit <verdict>
# ---------------------------------------------------------------------------
# An UNMAPPED verdict refuses. It must never fall through to the good exit,
# which is what a `case ... *) exit 0` written by hand does, and what the naive
# artifact vendored as this control's anchor does on purpose.
gate_exit() {
    _gate_require_map gate_exit
    [ $# -eq 1 ] || _gate_refuse "gate_exit needs exactly one <verdict>; got $# argument(s)"

    if ! _gate_exit_code=$(_gate_code_for "$1"); then
        _gate_refuse \
            "gate_exit: '$1' is not in the declared map ($GATE_MAP); refusing rather than falling through to the good exit"
    fi

    exit "$_gate_exit_code"
}

# ---------------------------------------------------------------------------
# THE SELF-CHECK - this file's own instrument, and the control's gate
# ---------------------------------------------------------------------------
# DISPATCH IS ON A SENTINEL THIS FILE CARRIES, NOT ON `$0` OR `$1`. POSIX `.`
# passes the caller's positional parameters straight through, so `$1` belongs to
# whoever sourced us and a gate whose own CLI takes `--check` would run this
# instead of its work. `$0` is no better: when sourced it names the CALLER, so a
# basename test would also make the vendored ANCHOR - which has a different
# filename by construction - dispatch nothing, exit 0 on every case, and pass
# the anchor checks for entirely the wrong reason. A vacuous anchor is worse
# than no anchor, because it reads as a demonstration. The sentinel travels with
# the bytes, so the anchor keeps it and a sourcing gate never has it.
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
    trap 'printf "GATE_LIB_EXIT=%d\n" "$?" >&2' EXIT
    _gate_main "$@"
fi
