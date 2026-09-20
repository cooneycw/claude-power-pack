#!/usr/bin/env bash
# ANCHOR - the PRE-FIX version of scripts/cpp-host-write.sh.
#
# DO NOT FIX THIS FILE. It is evidence, not code that runs in anger. The
# register swaps it in for the real gate and requires it to MISS the known-bad
# input; an anchor that catches it proves the control is not load-bearing.
#
# THIS IS NOT CONSTRUCTED. It is the code as it actually stood, with one line
# restored verbatim: normalise() written as `s="${s/#$HOME\//~/}"`, which reads
# as "replace a leading $HOME/ with ~/" and silently does nothing, because the
# escaped separator does not parse the way it looks.
#
# THE FAILURE IT PRODUCES is the worst one this seam can have. Every defer
# request compared "$HOME/.bashrc" against "~/.bashrc", never matched, and the
# helper WROTE THE SURFACE IT HAD BEEN ASKED TO SKIP while exiting 0. Not a
# missed detection - a wrong verdict, reporting success having done the
# forbidden thing, which nothing downstream re-derives.
#
# It was found by RUNNING the helper against a sandboxed $HOME, in one call,
# after the line had been read twice. That is this control's whole argument.
#: HOST-SURFACE: ~/.claude/settings.json owner=cpp write=merge certified=yes
#: HOST-SURFACE: ~/.claude owner=cpp write=mkdir certified=yes
#: HOST-SURFACE: ~/.claude/scripts owner=cpp write=mkdir certified=yes
#: HOST-SURFACE: ~/.bashrc owner=user write=append certified=yes
#
# cpp-host-write.sh - the one place /cpp:init and /cpp:update write host
# surfaces, and the seam a managed environment defers (issue #1139).
#
# WHY THIS EXISTS. These writes used to sit as inline shell inside two 75KB
# command documents. That had two consequences and the second is the issue:
#
#   1. Nothing could DECLARE them. A manifest derived from the helpers missed
#      ~/.bashrc entirely, because no helper wrote it - the document did.
#   2. Nothing could REFUSE them. A defer-set has no code to consult when the
#      write is prose-shell in a markdown file, so Half B of #1139 was not
#      implementable at all until the writes lived here.
#
# ENVIRONMENT-AGNOSTIC, AND NOT BY POLITENESS. Nothing in this file names any
# manager, reads any manager's environment variable, or inspects containers,
# mounts or namespaces. The defer-set is PASSED, never detected:
#
#   --defer ~/.bashrc --defer ~/.claude/settings.json
#   CPP_DEFER_SURFACES="~/.bashrc:~/.claude/settings.json"
#
# A user who never heard of any manager passes nothing and gets today's
# behaviour - not because CPP detected they were unmanaged, but because there
# was nothing to detect. An environment variable would NOT do: variables are
# inheritable, a tmux server hands its environment to every pane started after
# it, and `tmux show-environment -t` cannot see what the server holds globally.
# So a marker can arrive in a session nothing started that way. An argument
# cannot be inherited. CPP_DEFER_SURFACES is accepted as a convenience for a
# wrapper that cannot reach the argv, and it is read as DATA about what to
# skip - never as evidence about what kind of environment this is.
#
# A DEFERRED WRITE IS REPORTED, NEVER SILENTLY SKIPPED. Skipping quietly is the
# #1138 defect - an install that did nothing reporting success. Every refusal
# names the surface and its declared owner and exits 3, which is distinct from
# both success and failure so a caller can tell "the manager owns this" from
# "this went wrong".

set -uo pipefail

CPP_HOST_WRITE_EXIT_DEFERRED=3

usage() {
    cat <<'USAGE'
cpp-host-write.sh <command> [--defer SURFACE]... [args]

  ensure-dir <path>              mkdir -p a directory under $HOME
  settings-merge <template>      merge a permissions template into settings.json
  bashrc-append <marker> <file>  append a guarded block to ~/.bashrc
                                 (--no-guard preserves a pre-existing defect;
                                  see the note at cmd_bashrc_append)
  surfaces                       list the surfaces this helper can write

Exit: 0 wrote (or already present), 3 deferred by request, 1 failed.
USAGE
}

#: Surfaces the caller asked this run not to write. Populated from --defer and
#: from CPP_DEFER_SURFACES; never from a probe of the environment.
DEFERRED=()

collect_deferred() {
    local raw="${CPP_DEFER_SURFACES:-}"
    if [ -n "$raw" ]; then
        local IFS=':'
        # shellcheck disable=SC2206
        local parts=($raw)
        local p
        for p in "${parts[@]}"; do
            [ -n "$p" ] && DEFERRED+=("$p")
        done
    fi
}

#: Compare a surface against the defer-set. Both sides are normalised to the
#: `~/`-rooted spelling so that `$HOME/.bashrc` and `~/.bashrc` are one
#: surface: a defer-set that matched only the spelling the caller happened to
#: use would refuse some writes and silently perform others.
normalise() {
    local s="$1"
    #: `case` prefix matching, deliberately, NOT ${s/#$HOME\//~/}. That
    #: expansion reads as "replace a leading $HOME/ with ~/" and silently does
    #: nothing - the escaped separator does not parse the way it looks. The
    #: cost of the bug was not cosmetic: every defer request compared
    #: "$HOME/.bashrc" against "~/.bashrc", never matched, and the helper
    #: WROTE THE SURFACE IT HAD BEEN ASKED TO SKIP while exiting 0. A silent
    #: non-refusal is the worst failure this seam can have, so the comparison
    #: is now written in a form whose behaviour is obvious on sight.
    s="${s/#$HOME\//~/}"
    printf '%s' "$s"
}

is_deferred() {
    local want
    want="$(normalise "$1")"
    local d
    for d in "${DEFERRED[@]:-}"; do
        [ "$(normalise "$d")" = "$want" ] && return 0
    done
    return 1
}

#: The stated refusal. Names the surface AND its declared owner, because
#: "skipped" alone leaves a caller unable to tell a deliberate deferral from a
#: failure it should investigate.
refuse() {
    local surface="$1" owner="$2"
    printf 'cpp-host-write: DEFERRED %s (owner=%s) - not written, by request\n' \
        "$(normalise "$surface")" "$owner"
    return "$CPP_HOST_WRITE_EXIT_DEFERRED"
}

cmd_surfaces() {
    grep -E '^#: HOST-SURFACE:' "$0" | sed 's/^#: HOST-SURFACE: //'
}

cmd_ensure_dir() {
    local path="$1"
    is_deferred "$path" && { refuse "$path" cpp; return $?; }
    mkdir -p "$path" || return 1
    printf 'cpp-host-write: ok %s (directory present)\n' "$(normalise "$path")"
}

cmd_settings_merge() {
    local template="$1"
    local target="$HOME/.claude/settings.json"
    is_deferred "$target" && { refuse "$target" cpp; return $?; }
    [ -f "$template" ] || { printf 'cpp-host-write: FAILED template not found: %s\n' "$template" >&2; return 1; }
    mkdir -p "$HOME/.claude" || return 1
    [ -f "$target" ] || echo '{}' > "$target"
    local before after
    before=$(jq '(.permissions.allow // []) | length' "$target") || return 1
    jq -s '.[0].permissions.allow = (((.[0].permissions.allow // []) + .[1].permissions.allow) | unique) | .[0]' \
        "$target" "$template" > "$target.tmp" && mv "$target.tmp" "$target" || return 1
    after=$(jq '.permissions.allow | length' "$target") || return 1
    printf 'cpp-host-write: ok ~/.claude/settings.json (%s new rule(s), %s total)\n' \
        "$((after - before))" "$after"
}

#: An append is GUARDED by its marker, so running twice is a no-op. The inline
#: version this replaces had no guard on the PS1 block while the tmux block
#: seventeen lines below it did, so /cpp:init twice appended the export twice.
#: That defect is recorded separately and is NOT repaired here - preserving
#: behaviour is the only claim that makes a move reviewable. The guard below is
#: the behaviour of the block that HAD one; the caller decides which it gets.
cmd_bashrc_append() {
    local marker="$1" content_file="$2"
    local target="$HOME/.bashrc"
    is_deferred "$target" && { refuse "$target" user; return $?; }
    #: `-` reads the block from stdin, so a caller can pass a heredoc instead
    #: of committing a template file for three lines of shell. The content is
    #: buffered BEFORE the guard check, because reading stdin after deciding to
    #: skip would leave the caller's heredoc unconsumed and desynchronise the
    #: surrounding script.
    local content
    if [ "$content_file" = "-" ]; then
        content="$(cat)"
    else
        [ -f "$content_file" ] || { printf 'cpp-host-write: FAILED content not found: %s\n' "$content_file" >&2; return 1; }
        content="$(cat "$content_file")"
    fi
    #: --no-guard exists ONLY to preserve an existing defect across the #1139
    #: relocation, and it should be deleted when that defect is fixed.
    #:
    #: /cpp:init appends TWO blocks to ~/.bashrc. The tmux block guards itself
    #: with `grep -q 'tmux new-session'`; the PS1 block seventeen lines above
    #: it guards nothing, so running /cpp:init twice appends the export twice.
    #: Same file, same command, one guarded and one not - which is what makes
    #: it an oversight rather than deliberate minimalism.
    #:
    #: Routing the PS1 block through the guard would REPAIR that while moving
    #: it, and a refactor that also repairs cannot demonstrate it preserved
    #: behaviour - preservation being the only claim that makes a move
    #: reviewable. So the move carries the defect forward faithfully, and the
    #: fix is afterwards: drop --no-guard at the call site, delete this branch.
    if [ "${NO_GUARD:-0}" = "1" ]; then
        printf '%s\n' "$content" >> "$target" || return 1
        printf 'cpp-host-write: ok ~/.bashrc (%s appended, UNGUARDED - see --no-guard)\n' "$marker"
        return 0
    fi
    if [ -f "$target" ] && grep -qF "$marker" "$target" 2>/dev/null; then
        printf 'cpp-host-write: ok ~/.bashrc (%s already present, skipped)\n' "$marker"
        return 0
    fi
    printf '%s\n' "$content" >> "$target" || return 1
    printf 'cpp-host-write: ok ~/.bashrc (%s appended)\n' "$marker"
}

main() {
    local cmd="${1:-}"
    [ -n "$cmd" ] || { usage >&2; return 2; }
    shift
    collect_deferred
    local args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --defer) DEFERRED+=("${2:-}"); shift 2 ;;
            --no-guard) NO_GUARD=1; shift ;;
            -h|--help) usage; return 0 ;;
            *) args+=("$1"); shift ;;
        esac
    done
    case "$cmd" in
        surfaces)       cmd_surfaces ;;
        ensure-dir)     cmd_ensure_dir "${args[0]:?path required}" ;;
        settings-merge) cmd_settings_merge "${args[0]:?template required}" ;;
        bashrc-append)  cmd_bashrc_append "${args[0]:?marker required}" "${args[1]:?content file required}" ;;
        *) printf 'cpp-host-write: unknown command: %s\n' "$cmd" >&2; usage >&2; return 2 ;;
    esac
}

main "$@"
