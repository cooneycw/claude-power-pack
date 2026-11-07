#!/usr/bin/env bash
# coordination-admission.sh - the shared rollout signal for service coordination.
#
# Sourced by flow-finish-gate.sh and gh-pr-merge.sh, which call
# coordination_admission_on. Run directly, it reports what those callers would
# decide right now:
#
#   bash coordination-admission.sh        COORDINATION_ADMISSION: on|off  (exit 0)
#   bash coordination-admission.sh --help this text                       (exit 0)
#   anything else                         usage                           (exit 2)
#
# The owner writes this operator-config flag only at the joint switch. Read it
# for every invocation so an already-running session observes the same switch.
# CPP_COORDINATION_ADMISSION_FILE is a test hook only; never set it in
# operational environments. Only the dedicated coordination directory is shared
# read-only with containers, so replacing/removing admission stays visible.
# Exact bytes on + newline activate; unknown input silently keeps the old path.
coordination_admission_on() {
    local flag="${CPP_COORDINATION_ADMISSION_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/claude-power-pack/coordination/admission}"
    [[ -f "$flag" && -r "$flag" && ! -L "$flag" ]] || return 1
    cmp -s -- "$flag" <(printf 'on\n') 2>/dev/null
}

# Direct execution only. Sourced, BASH_SOURCE[0] is this file and $0 is the
# caller, so neither the status report nor the exit line runs. The exit line is
# also installed only when no EXIT trap exists, so it can never replace a
# caller's own marker (the gate-lib.sh rule, #1061).
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    if [[ -z "$(trap -p EXIT 2>/dev/null)" ]]; then
        trap 'printf "COORDINATION_ADMISSION_EXIT=%d\n" "$?" >&2' EXIT
    fi
    case "${1:-}" in
        "")
            if coordination_admission_on; then
                echo "COORDINATION_ADMISSION: on"
            else
                echo "COORDINATION_ADMISSION: off"
            fi
            exit 0
            ;;
        -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
        *) echo "usage: bash $0 [--help]" >&2; exit 2 ;;
    esac
fi
