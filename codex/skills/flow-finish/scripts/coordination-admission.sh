#!/usr/bin/env bash
# The owner writes this operator-config flag only at the joint switch. Read it
# for every invocation so an already-running session observes the same switch.
# CPP_COORDINATION_ADMISSION_FILE is a test hook only; never set it in
# operational environments. The owner switches the default shared config file.
# Exact bytes on + newline activate; unknown input silently keeps the old path.
coordination_admission_on() {
    local flag="${CPP_COORDINATION_ADMISSION_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/claude-power-pack/coordination-admission}"
    [[ -f "$flag" && -r "$flag" && ! -L "$flag" ]] || return 1
    cmp -s -- "$flag" <(printf 'on\n') 2>/dev/null
}
