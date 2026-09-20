#!/usr/bin/env bash
#: HOST-SURFACE: none - refuses git stash from a linked worktree. --install writes a hook inside the REPO, not under $HOME.

# CPP-GUARD-ID: stash-worktree-guard
# stash-worktree-guard.sh - refuse `git stash push` from a LINKED WORKTREE
# (issue #1056).
#
# THE HAZARD. A linked worktree isolates the WORKING TREE and not the REFS. A
# stash entry lives at `refs/stash` in the repository's COMMON git dir, so every
# worktree of a repository shares ONE stash stack. With several agent sessions
# working in sibling worktrees, session A pushes, session B pushes on top, and
# A's `git stash pop` silently restores B's uncommitted work into A's checkout -
# no error, no warning, and A's own entry gone from the visible stack. Measured
# twice in this repository: #635 (two symmetric hits) and #1056 (a `/codex:auto`
# worker on #1032 popped 67 lines of a different session's #1027 work).
#
# WHY THIS EXISTS RATHER THAN THE DOCUMENTED RULE. #635 fixed the two flow
# commands by writing "never stash here" into `.claude/commands/flow/auto.md`
# and `finish.md`. A rule written in the documents that describe the SAFE paths
# binds only a caller who is reading one of those documents at that moment. It
# did not bind the #1056 worker, who was producing a RED case against pre-fix
# code - a task no flow command covers - and it does not bind a human, a Codex
# worker, a Qwen worker, or anything else that reaches for `git stash` ad hoc.
# A `reference-transaction` hook binds all of them, because it lives in git.
#
# ---------------------------------------------------------------------------
# WHAT THIS GUARDS, AND WHAT IT CANNOT - READ THIS BEFORE TRUSTING ITS SILENCE
# ---------------------------------------------------------------------------
# It guards `git stash push` ONLY. It does NOT guard `pop`, `drop` or `clear`,
# and it never can from this hook. Measured on git 2.43.0 while building it:
#
#   push   refs/stash transaction is `prepared` BEFORE the working tree is
#          touched, so refusing aborts cleanly: exit 128, WORKING TREE BYTE
#          IDENTICAL, no entry created. This is the case that is guarded.
#   pop    git applies the stash to the working tree and prints
#          `Dropped refs/stash@{0}` FIRST; the veto fires afterwards. Refusing
#          there leaves the tree mutated AND the entry gone - strictly worse
#          than not guarding. So this hook deliberately ignores it.
#   drop   same shape: `Dropped` precedes the hook.
#
# That asymmetry is why this file refuses only the CREATION of a stash entry -
# `old` is the null OID, which is the exact and only signature `stash push`
# presents at `prepared`. A future editor who "completes" this guard by acting
# on deletions too will not be widening it; they will be adding a refusal that
# fires after the damage. `tests/test_stash_worktree_guard.py` pins the
# limitation so that edit fails loudly instead of reading as an improvement.
#
# Stopping the push is still the load-bearing half: a caller refused at the push
# never reaches the pop, and every entry not created is an entry no sibling can
# take.
#
# ---------------------------------------------------------------------------
# CONTRACT
# ---------------------------------------------------------------------------
#   FAIL-OPEN everywhere except the one case above. Another ref, another
#   transaction state, an unreadable line, a git too old to resolve its own
#   dirs - all exit 0. This hook fires on EVERY ref update in the repository
#   (every commit, fetch and branch), so a bug here breaks git for every session
#   in every worktree. It does no work at all until a line's ref is already
#   known to be `refs/stash`.
#
#   THE RECORDED PREFERENCE IS AUTHORITATIVE, not the hook file's presence.
#   The hook itself reads `cpp.stashGuard` before refusing, so a repository that
#   opted out is unguarded even when a hook file exists - which it can, if an
#   absolute `core.hooksPath` is shared with a neighbouring repository that
#   installed one.
#
#   ESCAPE HATCH: `CPP_ALLOW_WORKTREE_STASH=1` permits the push, for the
#   deliberate uniquely-tagged stash that is restored by `git stash apply <sha>`
#   rather than a bare pop. Set it in the SAME command:
#     CPP_ALLOW_WORKTREE_STASH=1 git stash push -u -m "my-unique-tag"
#
# Usage:
#   stash-worktree-guard.sh <state>      # as the reference-transaction hook
#   stash-worktree-guard.sh --install [REPO]    # install into REPO (default: cwd)
#   stash-worktree-guard.sh --check   [REPO]    # report, change nothing
#   stash-worktree-guard.sh --uninstall [REPO]  # remove it AND record the opt-out
#   stash-worktree-guard.sh --enable  [REPO]    # clear the opt-out and install
#   ... plus --quiet, for the automatic callers: silent when nothing happened.
#
# INSTALLATION IS ON BY DEFAULT (owner decision, 2026-09-19): `/cpp:init`,
# `/cpp:update` and the flow worktree lane all call `--install`. Turning it off
# is `--uninstall`, which PERSISTS the choice as `cpp.stashGuard=false` in the
# repository config - without that, the next automatic install would silently
# undo it and the user would be answering the same question every update.
#
# --install / --check / --uninstall / --enable end with a machine-readable
# verdict line:
#   STASH_GUARD: installed | current | stale | absent | foreign | unsupported
#                | disabled | error
#
#   `disabled` is the recorded opt-out, and it exits 0 - it is a settled state
#   chosen by the user, not a fault for an automatic caller to repair.
#
#   `foreign` means a DIFFERENT reference-transaction hook is already there.
#   Installing over it is refused rather than silently chained: a hook that
#   fires on every ref update is not something to overwrite on a guess.
#   `unsupported` means git is older than 2.28 and has no reference-transaction
#   hook at all - the guard cannot bind there and says so rather than reporting
#   a successful install that enforces nothing.
#
# The hook location is resolved with `git rev-parse --git-path hooks`, so a
# repository that sets an ABSOLUTE `core.hooksPath` is installed and checked
# where git actually reads - not where the common dir would suggest. A RELATIVE
# `core.hooksPath` is refused as `unsupported`: each worktree resolves it against
# its own top-level, so no single install can cover the family that shares the
# stack, and reporting success there would claim coverage that does not exist.
#
# The installed copy is a COPY, never a symlink. A symlink into a checkout that
# is later moved or deleted leaves a dangling hook in every worktree of the
# repository; `--check` reports a stale copy, which is recoverable, while a
# dangling hook is a repository that has to be repaired before it can be used.
#
# See docs/agents/shared-stash-stack.md for the mechanism and the safe
# alternatives to stashing.

set -u

GUARD_ID="CPP-GUARD-ID: stash-worktree-guard"

# --------------------------------------------------------------------------
# Installer / reporter lane. Git never passes these as a hook state.
# --------------------------------------------------------------------------
_self() {
    local src="${BASH_SOURCE[0]:-$0}"
    ( cd "$(dirname "$src")" 2>/dev/null && printf '%s/%s' "$(pwd -P)" "$(basename "$src")" )
}

_hooks_dir() {
    # Ask git where hooks ACTUALLY live, rather than assuming the common dir's
    # `hooks/`. `core.hooksPath` overrides that location, and a host that sets it
    # would otherwise get an install into a directory git never reads - reported
    # as success while every worktree push stayed unguarded. Found by the
    # counter-model review on this branch; verified that `--git-path hooks`
    # returns the override from the main checkout AND from a linked worktree.
    #
    # One hook still binds the whole worktree family: `--git-path hooks` resolves
    # to the same place from every worktree, which is exactly the population that
    # shares the stash stack.
    local repo="$1" hooks
    hooks="$(git -C "$repo" rev-parse --git-path hooks 2>/dev/null)" || return 1
    [ -n "$hooks" ] || return 1
    case "$hooks" in
        /*) printf '%s' "$hooks" ;;
        *)  printf '%s/%s' "$(cd "$repo" 2>/dev/null && pwd -P)" "$hooks" ;;
    esac
}

#: THE OPT-OUT IS A PERSISTED REPOSITORY PREFERENCE, and it has to be, because
#: installation is now automatic (`/cpp:init`, `/cpp:update`, and the flow
#: worktree lane all call `--install`). An opt-out that the next automatic
#: install silently overwrites is not an opt-out - it is a prompt the user
#: answers again every update, which is the oscillation ADR 0009 predicts
#: arriving as the remedy rather than the problem. So:
#:
#:   --uninstall   removes the hook AND records `cpp.stashGuard=false`
#:   --install     honours that record and reports `disabled`, changing nothing
#:   --enable      clears the record and installs (the deliberate way back on)
#:
#: `git config` without `--worktree` writes the COMMON config, which is right:
#: the guard is a property of the repository, exactly like the stack it guards.
#: Recording the preference is the whole mechanism, so a FAILED write must never
#: be reported as a recorded one. `git config ... || true` claimed the opt-out
#: while a `.git/config.lock` silently discarded it, and the next automatic
#: install then reinstalled over a choice the user was told had been saved
#: (counter-model finding).
_set_opt_out() {
    git -C "$1" config cpp.stashGuard false 2>/dev/null
}

_clear_opt_out() {
    # `--unset-all` exits 5 when the key is simply not there, which is success
    # for our purposes and must be told apart from a real write failure - the
    # difference between "already on" and "still recorded off while we install
    # an enforcing hook", which would make --check report `disabled` about a
    # repository that refuses stashes.
    local rc
    git -C "$1" config --unset-all cpp.stashGuard 2>/dev/null
    rc=$?
    [ "$rc" -eq 0 ] || [ "$rc" -eq 5 ]
}

_opt_out() {
    local repo="$1" v
    v="$(git -C "$repo" config --get cpp.stashGuard 2>/dev/null || printf '')"
    case "$v" in
        false|off|0|no) return 0 ;;
        *) return 1 ;;
    esac
}

_git_supports_hook() {
    # reference-transaction arrived in git 2.28.
    local v major minor
    v="$(git --version 2>/dev/null | awk '{print $3}')" || return 1
    major="${v%%.*}"; v="${v#*.}"; minor="${v%%.*}"
    [ -n "$major" ] && [ -n "$minor" ] || return 1
    [ "$major" -gt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -ge 28 ]; }
}

_admin() {
    local action="$1" repo="${2:-.}" self target
    self="$(_self)"

    if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
        echo "stash-worktree-guard: '$repo' is not a git repository." >&2
        echo "STASH_GUARD: error"
        return 1
    fi

    # A RELATIVE core.hooksPath cannot deliver what this guard promises.
    # Measured: each worktree resolves a relative hooksPath against its OWN
    # top-level, so `main/.githooks` is not read by `../wt` at all - one install
    # would leave every sibling unguarded while reporting success. Refuse rather
    # than claim family-wide coverage the configuration cannot provide (found by
    # the counter-model review on this branch; an ABSOLUTE hooksPath is shared by
    # the whole family and is supported normally).
    local hooks_cfg
    hooks_cfg="$(git -C "$repo" config --get core.hooksPath 2>/dev/null || printf '')"
    if [ -n "$hooks_cfg" ]; then
        case "$hooks_cfg" in
            /*) ;;
            *)
                echo "stash-worktree-guard: core.hooksPath is RELATIVE ('$hooks_cfg')." >&2
                echo "  Each worktree resolves that against its own top-level, so one install" >&2
                echo "  cannot cover the worktree family that shares the stash stack - and a" >&2
                echo "  success here would claim coverage this configuration cannot give." >&2
                echo "  Set an ABSOLUTE core.hooksPath, or unset it, then re-run." >&2
                echo "STASH_GUARD: unsupported"
                return 1
                ;;
        esac
    fi

    if ! _git_supports_hook; then
        echo "stash-worktree-guard: git $(git --version 2>/dev/null | awk '{print $3}') has no" >&2
        echo "  reference-transaction hook (needs 2.28+). The guard cannot bind on this host." >&2
        echo "STASH_GUARD: unsupported"
        return 1
    fi

    target="$(_hooks_dir "$repo")" || { echo "STASH_GUARD: error"; return 1; }
    target="$target/reference-transaction"

    if _opt_out "$repo" && [ "$action" != "enable" ]; then
        # Say whether a hook file is nonetheless present - with a shared
        # absolute core.hooksPath a neighbour repository can have created one.
        # It is INERT here (the hook consults this repository's preference
        # before refusing), but reporting `disabled` while a file sits there
        # would describe the preference and leave the reader to assume the
        # behaviour (counter-model finding).
        local _t
        if _t="$(_hooks_dir "$repo")" && [ -e "$_t/reference-transaction" ]; then
            echo "stash-worktree-guard: a hook FILE is present at $_t/reference-transaction" >&2
            echo "  (likely a neighbour repository sharing core.hooksPath). It is inert here:" >&2
            echo "  the hook reads this repository's cpp.stashGuard before refusing anything." >&2
        fi
        # Not an error and not a failure: the user turned it off on purpose.
        # Exit 0 so an automatic caller treats it as a settled state rather than
        # something to repair.
        echo "stash-worktree-guard: disabled for this repository (cpp.stashGuard=false)."
        echo "  Re-enable with: stash-worktree-guard.sh --enable $repo"
        echo "STASH_GUARD: disabled"
        return 0
    fi

    case "$action" in
        check)
            if [ ! -e "$target" ]; then
                echo "stash-worktree-guard: not installed at $target"
                echo "STASH_GUARD: absent"
                return 1
            fi
            if ! grep -qF "$GUARD_ID" "$target" 2>/dev/null; then
                echo "stash-worktree-guard: a DIFFERENT reference-transaction hook is at $target" >&2
                echo "STASH_GUARD: foreign"
                return 1
            fi
            if ! [ -x "$target" ]; then
                # git SILENTLY IGNORES a non-executable hook (it prints an advice
                # hint and proceeds). Byte-identical content therefore says
                # nothing about whether anything is enforced, and reporting
                # `current` here would claim enforcement this run did not
                # establish. Found by the counter-model review on this branch.
                echo "stash-worktree-guard: installed but NOT EXECUTABLE at $target" >&2
                echo "  git ignores a non-executable hook, so nothing is enforced. Re-run --install." >&2
                echo "STASH_GUARD: stale"
                return 1
            fi
            if cmp -s "$self" "$target"; then
                echo "stash-worktree-guard: current at $target"
                echo "STASH_GUARD: current"
                return 0
            fi
            echo "stash-worktree-guard: installed but STALE at $target (re-run --install)" >&2
            echo "STASH_GUARD: stale"
            return 1
            ;;
        enable)
            if ! _clear_opt_out "$repo"; then
                echo "stash-worktree-guard: could NOT clear cpp.stashGuard in $repo." >&2
                echo "  Installing anyway would leave the config saying 'off' while the" >&2
                echo "  hook refuses - so nothing was changed." >&2
                echo "STASH_GUARD: error"
                return 1
            fi
            echo "stash-worktree-guard: re-enabled for this repository."
            ;&
        install)
            if [ -e "$target" ] && ! grep -qF "$GUARD_ID" "$target" 2>/dev/null; then
                echo "stash-worktree-guard: REFUSING to overwrite a different" >&2
                echo "  reference-transaction hook at $target" >&2
                echo "  That hook fires on every ref update in this repository. Merge the two" >&2
                echo "  by hand, or move it aside deliberately, then re-run." >&2
                echo "STASH_GUARD: foreign"
                return 1
            fi
            # ALREADY CURRENT is its own verdict, not a fresh install. The
            # automatic callers run --install on every flow worktree, so an
            # install that always claims `installed` makes `--quiet` useless and
            # puts a line in front of the user on every single run - which is how
            # a guard becomes noise people learn to skip past.
            if [ -e "$target" ] && [ -x "$target" ] && cmp -s "$self" "$target"; then
                echo "stash-worktree-guard: current at $target"
                echo "STASH_GUARD: current"
                return 0
            fi
            mkdir -p "$(dirname "$target")" || { echo "STASH_GUARD: error"; return 1; }
            cp "$self" "$target" || { echo "STASH_GUARD: error"; return 1; }
            chmod +x "$target" || { echo "STASH_GUARD: error"; return 1; }
            echo "stash-worktree-guard: installed at $target"
            echo "  Guards \`git stash push\` from a linked worktree. Does NOT guard pop/drop"
            echo "  (measured: git drops the entry before the hook can veto) - see the header."
            echo "STASH_GUARD: installed"
            return 0
            ;;
        uninstall)
            if [ ! -e "$target" ]; then
                # RECORD IT ANYWAY. Turning the guard off BEFORE it was ever
                # installed is the ordinary case now that installation is
                # automatic - and the early return wrote nothing, so the next
                # flow run installed it against a choice the user had already
                # made and been told was accepted (counter-model finding).
                if ! _set_opt_out "$repo"; then
                    echo "stash-worktree-guard: could NOT record the opt-out in $repo" >&2
                    echo "  (git config write failed - the guard would be reinstalled)" >&2
                    echo "STASH_GUARD: error"
                    return 1
                fi
                echo "stash-worktree-guard: nothing installed at $target"
                echo "  Recorded cpp.stashGuard=false, so nothing will install it. Undo with --enable."
                echo "STASH_GUARD: absent"
                return 0
            fi
            if ! grep -qF "$GUARD_ID" "$target" 2>/dev/null; then
                echo "stash-worktree-guard: $target is NOT our hook - refusing to remove it." >&2
                echo "STASH_GUARD: foreign"
                return 1
            fi
            rm -f "$target" || { echo "STASH_GUARD: error"; return 1; }
            # RECORD the choice, or the next automatic install undoes it - and
            # a write that FAILED must not be announced as one that worked.
            if ! _set_opt_out "$repo"; then
                echo "stash-worktree-guard: hook removed, but could NOT record the opt-out" >&2
                echo "  in $repo - the next automatic install will bring it back." >&2
                echo "STASH_GUARD: error"
                return 1
            fi
            echo "stash-worktree-guard: removed $target"
            echo "  Recorded cpp.stashGuard=false, so /cpp:init, /cpp:update and the"
            echo "  flow worktree lane will not reinstall it. Undo with --enable."
            echo "STASH_GUARD: absent"
            return 0
            ;;
    esac
}

#: `--quiet` exists for the AUTOMATIC callers (the flow worktree lane runs this
#: on every `--verify`). Silent when nothing happened - `current` or `disabled` -
#: and fully verbose when it did, so a first install still announces itself and
#: a `foreign`/`unsupported` refusal is never swallowed. Buffering the output and
#: deciding on the verdict keeps ONE code path for both modes: a separate quiet
#: path would be a second implementation that could drift from this one.
_run_admin() {
    local action="$1" repo="$2" quiet="$3" out rc
    out="$(_admin "$action" "$repo" 2>&1)"; rc=$?
    if [ "$quiet" = "1" ]; then
        case "$out" in
            *"STASH_GUARD: current"*|*"STASH_GUARD: disabled"*)
                # Suppress the PROSE, never the verdict. `--quiet` exists so a
                # no-op does not put a line in front of a human on every flow
                # worktree; the STASH_GUARD: marker is the machine contract its
                # callers parse, and silencing that turned a real `disabled`
                # into `unknown` in the resolver - an opt-out rendering as "could
                # not tell". Caught by
                # test_verify_honours_the_stash_guard_optout.
                printf '%s\n' "$out" | grep '^STASH_GUARD:'
                return "$rc"
                ;;
        esac
    fi
    printf '%s\n' "$out"
    return "$rc"
}

_ACTION=""; _REPO=""; _QUIET=0
for _arg in "$@"; do
    case "$_arg" in
        --install)   _ACTION="install" ;;
        --enable)    _ACTION="enable" ;;
        --check)     _ACTION="check" ;;
        --uninstall) _ACTION="uninstall" ;;
        --quiet)     _QUIET=1 ;;
        -*)          ;;
        *)           [ -z "$_REPO" ] && _REPO="$_arg" ;;
    esac
done
if [ -n "$_ACTION" ]; then
    # Exit status on stderr so it survives `| tail` (issue #1031) - ADMIN LANE
    # ONLY. The hook lane below runs on EVERY ref update, so a line there would
    # print on every `git commit` and `git fetch` in every repository carrying
    # the guard - a guard that makes ordinary git noisy is a guard people remove.
    trap 'printf "STASH_GUARD_EXIT=%d\n" "$?" >&2' EXIT
    _run_admin "$_ACTION" "${_REPO:-.}" "$_QUIET"
    exit $?
fi

# --------------------------------------------------------------------------
# Hook lane. Everything below runs on EVERY ref update: stay cheap, fail open.
# --------------------------------------------------------------------------
[ "${1:-}" = "prepared" ] || exit 0
[ "${CPP_ALLOW_WORKTREE_STASH:-}" = "1" ] && exit 0

# All-zeros of any width: git's null OID is 40 hex zeros (SHA-1) or 64 (SHA-256).
# An EMPTY value is NOT null - it is a malformed line, and malformed means
# fail-open, not "act".
_is_null() { case "$1" in '' | *[!0]*) return 1 ;; *) return 0 ;; esac; }

_abs() { ( cd "$1" 2>/dev/null && pwd -P ) || printf '%s' "$1"; }

while read -r old new ref _rest; do
    [ "${ref:-}" = "refs/stash" ] || continue

    # The CREATION signature, and the only one `stash push` presents here:
    # old is the null OID, new is a real object. A deletion (pop/drop) is the
    # other direction and is deliberately not acted on - see the header.
    _is_null "${old:-}" || continue
    _is_null "${new:-}" && continue

    gd="$(git rev-parse --git-dir 2>/dev/null)" || exit 0
    gcd="$(git rev-parse --git-common-dir 2>/dev/null)" || exit 0
    [ -n "$gd" ] && [ -n "$gcd" ] || exit 0
    gd="$(_abs "$gd")"; gcd="$(_abs "$gcd")"
    [ "$gd" != "$gcd" ] || exit 0   # main checkout - permitted, as configured

    # THE OPT-OUT IS CHECKED HERE, IN THE HOOK, not only by the installer.
    # The hook FILE's presence is not the source of truth for enforcement: an
    # absolute `core.hooksPath` can be shared by independent repositories, so a
    # neighbour's install recreates this file in a repository that opted out -
    # and `--check` would then report `disabled` from the config while this code
    # went on refusing that repository's stashes. The recorded PREFERENCE is
    # authoritative, so consult it where the refusal actually happens
    # (counter-model finding). Cheap: nothing below the `refs/stash` test runs
    # on an ordinary ref update.
    case "$(git config --get cpp.stashGuard 2>/dev/null || printf '')" in
        false|off|0|no) exit 0 ;;
    esac

    {
        echo "stash-worktree-guard: REFUSED - \`git stash push\` from a linked worktree."
        echo
        echo "  worktree git dir : $gd"
        echo "  shared common dir: $gcd"
        echo
        echo "  The stash stack lives at refs/stash in the COMMON dir, so it is SHARED with"
        echo "  the main checkout and every sibling worktree. Another session's \`git stash"
        echo "  pop\` would take this entry and land it in their checkout (issue #1056)."
        echo
        echo "  Your working tree has NOT been changed and no entry was created."
        echo
        echo "  Set the work aside with a branch-local WIP commit instead - a sibling"
        echo "  session cannot take a commit, and a later squash flattens it:"
        echo "      git add -A && git commit -m \"wip: snapshot\""
        echo "  To read pre-fix content without stashing at all:"
        echo "      git show <base>:<path> > /tmp/pre-fix"
        echo "  See docs/agents/shared-stash-stack.md for the mechanism and alternatives."
        echo
        echo "  If you genuinely need a stash here, take ownership of the entry - tag it,"
        echo "  and restore it with \`git stash apply <sha>\`, NEVER a bare pop:"
        echo "      CPP_ALLOW_WORKTREE_STASH=1 git stash push -u -m \"<unique-tag>\""
        echo
        echo "  NOTE: this guard covers \`push\` only. \`pop\`, \`drop\` and \`clear\` are NOT"
        echo "  guarded and cannot be from this hook - git removes the entry before the"
        echo "  hook can refuse. Its silence on those is not approval."
    } >&2
    exit 1
done

exit 0
