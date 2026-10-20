#!/bin/bash
# worktree-remove.sh - Safely remove git worktrees
#
# If you're inside the worktree being removed, the script automatically
# changes to the main repository first (determined from the worktree's
# .git file) to prevent breaking your shell session.
#
# A worktree CLAIMED by another live /flow session (issue #597) is never
# removed: the claim is checked first and a live identified owner is a hard stop
# (exit 4), because removing it is exactly the silent-data-loss failure that
# motivated the claim. A self-owned or stale claim is released and removed as
# usual, and --steal is the deliberate override. A lock that does not identify
# a /flow session is only a warning; the independent safety checks below decide
# whether removal is safe.
#
# A claim only protects a worktree where one was staked, though, and `free`,
# `unsupported` and `unknown` are not claims. So a worktree that no claim names
# is checked a second way (issues #888 and #1032): if a live process has its
# working directory inside it, removal is refused (exit 5), whether the tree is
# currently dirty or clean. --force does NOT suppress that refusal - --force is
# what every /flow:auto Step 7 passes, so a guard it silences never fires where
# the damage happens. --steal overrides it as usual. On a host with no readable
# /proc the check reports `unknown` and falls open, rather than reporting a clean
# result it did not establish.
#
# THE BRANCH IDENTIFIES THE WORK, NOT THE DIRECTORY NAME (issue #1032). A
# worktree folder is named for the issue it was created for, but the name is a
# string and nothing keeps it in step with what is checked out inside. Observed
# here: a folder named `...-issue-971-...` (CLOSED, merged) holding the branch
# `issue-980-...` (OPEN). This script therefore reports
# `WORKTREE_REMOVE_ATTRIBUTION:` naming the branch as authoritative, and when
# the two disagree it REFUSES --delete-branch (exit 8): removing a directory is
# recoverable, deleting the wrong issue's branch is not. --force does not
# override it; --steal does.
#
# Usage:
#   worktree-remove.sh <worktree-path> [--force] [--delete-branch] [--steal] [--allow-dirty] [--allow-unpushed]
#   worktree-remove.sh <worktree-path> --finish-partial-removal --owner-repo <path> --allow-dirty
#
# Options:
#   --force          Pass --force to git worktree remove; does not override
#                    any data-loss refusal
#   --delete-branch  Also delete the associated branch after removal
#   --steal          Remove even when another live session claims it (#597),
#                    or when it is in use by a live process (#888, #1032)
#   --allow-dirty    Remove even though uncommitted work would be destroyed
#                    (implies --force: git worktree remove makes its own
#                    separate dirty-tree judgment that --allow-dirty alone
#                    does not clear, Nit Store #864)
#   --allow-unpushed Remove even though commits exist on no remote ref
#   --finish-partial-removal
#                    VERIFY (never remove) a worktree already left half-
#                    deleted (no .git file, directory still present).
#                    Requires --owner-repo AND --allow-dirty (there is no
#                    .git left to ask whether the directory is clean, so
#                    this path cannot be trusted by default). ALSO requires
#                    --allow-unpushed, but only when the owner's own
#                    objects/remote refs show the worktree's HEAD is
#                    actually unreachable from a remote - unlike dirtiness,
#                    this IS verifiable even with no .git file. On success
#                    this PRINTS the exact `rm -rf` command for a human to
#                    run; it does not run it. See POSITIVE OWNERSHIP, and
#                    VERIFY-AND-PRINT, below (issue #1524).
#   --owner-repo <path>
#                    The repository whose OWN `git worktree list --porcelain`
#                    must positively list the target as prunable before
#                    anything is printed. Required by, and meaningless
#                    without, --finish-partial-removal.
#
# POSITIVE OWNERSHIP, NEVER DISCOVERY (issue #1524). A half-deleted worktree
# has no .git file, so the normal path below - which derives the main
# repository FROM the worktree's own .git file - cannot run at all; there is
# nothing left to read. An earlier version of this flag (#1491, reverted
# 20e72086) tried to find the owner by searching sibling and ancestor
# directories for a repo that still lists the path. Three cross-model review
# passes each found a new variant of the same structural gap: a repo that
# TRUTHFULLY does not have the path registered answers "not registered"
# exactly like a repo that was simply never asked, and a proximity search
# cannot tell those apart. There is no global worktree registry to query, so
# "nobody nearby admits to owning this" can never mean "nobody owns this" -
# only "I did not ask the right repo". The redesign removes the search
# entirely: the caller must NAME the owner with --owner-repo, and that repo's
# own registry must say so, in git's own words - a `prunable` attribute on
# the exact matching record - or this script refuses. A read failure (the
# porcelain call itself fails) is also a refusal, never a silent "proceed
# because nothing said no".
#
# VERIFY-AND-PRINT, NOT AUTO-REMOVE (issue #1524, owner decision after a
# third review pass still found a real defect). Across three cross-model
# review passes on this flag's positive-ownership redesign, EACH pass found
# a genuine path-handling defect the previous pass's fix had not closed: a
# newline guard checking the wrong value, a missing dirty/unpushed
# requirement, `readlink -f`'s own trailing-newline loss, and finally a
# normalization step SHARED with the normal removal path below (see its own
# newline guard, right after "Worktree path is required") that could
# silently substitute a different target before any of this branch's checks
# ever ran. Three passes is this repository's ceiling for one change. Rather
# than ship a fourth attempt at automatic `rm -rf` with no further review,
# --finish-partial-removal now VERIFIES every precondition exactly as before
# (positive ownership, occupancy, the undeletable pre-scan, dirty, unpushed)
# and, on a pass, PRINTS the exact command for a human to run - it removes
# nothing itself. Every defect the three passes found was in path handling
# feeding an automatic deletion; none of them survive as a hazard once the
# deletion itself is a human's own typed (or pasted) command.
#
# `worktree prune` is deliberately never run OR printed as a ready command:
# it prunes every eligible stale entry in the owner's WHOLE registry, not
# only the one target this script verified, and could drop an unrelated
# stale worktree's registration that nothing here has checked. A
# `--dry-run --verbose` hint is printed instead, so a human can see exactly
# what pruning would affect before deciding to run it.
#
# A symlink in the PATH ITSELF is never named in the printed `rm -rf`. If the
# caller passes a path whose final component is a symlink pointing at the
# worktree, `rm -rf` on the symlink would remove only the link - the real
# worktree directory would survive untouched, an orphan indistinguishable
# from the outside from "this was never a worktree". This script resolves
# the input ONCE via `realpath`, before any comparison, and uses that
# resolved path for both the registry match and the printed command - never
# the caller's own symlink, which may live anywhere (a different repo, a
# home directory) and is not part of the worktree this script verifies.
#
# Exit codes:
#   0  removed (or already absent - stale refs pruned) - the NORMAL
#      (non---finish-partial-removal) path only
#   1  usage, path, or repository validation error
#   4  claimed by another live /flow session (#597)
#   5  in use by a live process (#888, #1032)
#   6  holds uncommitted work without --allow-dirty (#899)
#   7  holds commits on no remote ref without --allow-unpushed (#899)
#   8  --delete-branch asked for, but the directory name and the checked-out
#      branch name different issues (#1032)
#   9  a path inside the worktree (or its parent directory) cannot be deleted -
#      refused before anything is removed, rather than letting git report
#      success while files survive it (Nit Store #864)
#  10  --finish-partial-removal without --owner-repo, or --owner-repo without
#      --finish-partial-removal (#1524)
#  11  the argument, --owner-repo, or (for --finish-partial-removal) the
#      resolved target contains a literal newline - refused outright for
#      EVERY invocation, before normalization, never compared (#1524)
#  12  --owner-repo is not itself a readable git working tree (#1524)
#  13  --owner-repo's own registry does not positively list the resolved path
#      as prunable - no record, a record that is not prunable (e.g. locked),
#      or the registry could not be read at all (#1524)
#  14  --finish-partial-removal without --allow-dirty - there is no .git
#      left to verify the directory is clean, so this is required rather
#      than merely honoured (#1524)
#  15  --finish-partial-removal: VERIFIED, not removed - the `rm -rf`
#      command was printed for a human to run (#1524). A distinct, otherwise
#      unused code on purpose: under `set -euo pipefail` a failing `grep` or
#      a bash builtin misuse elsewhere in this script also exits 2, and this
#      path must never be confused with one of those. The
#      WORKTREE_REMOVE_FINISH_PARTIAL_VERIFIED line on stderr is the thing a
#      caller should key on, not the bare exit code alone.
#
# Examples:
#   worktree-remove.sh /home/user/Projects/nhl-api-issue-42
#   worktree-remove.sh /home/user/Projects/half-deleted-issue-9 \
#       --finish-partial-removal --owner-repo /home/user/Projects/main \
#       --allow-dirty --allow-unpushed
#   worktree-remove.sh ../nhl-api-issue-42 --delete-branch
#   worktree-remove.sh /home/user/Projects/nhl-api-issue-42 --force --delete-branch

set -euo pipefail

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "WORKTREE_REMOVE_EXIT=%d\n" "$?" >&2' EXIT

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
WORKTREE_PATH=""
FORCE=""
DELETE_BRANCH=false
STEAL=false
# Issue #899. Each data-loss refusal gets its OWN override, never --force and
# never each other's: three distinct refusals that one flag silences is one flag
# away from being no refusals, which is how #888's guard was lost.
ALLOW_DIRTY=false
ALLOW_UNPUSHED=false
FINISH_PARTIAL_REMOVAL=false
OWNER_REPO=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE="--force"
            shift
            ;;
        --delete-branch)
            DELETE_BRANCH=true
            shift
            ;;
        --finish-partial-removal)
            FINISH_PARTIAL_REMOVAL=true
            shift
            ;;
        --owner-repo)
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}Error: --owner-repo requires a value${NC}" >&2
                exit 1
            fi
            OWNER_REPO="$2"
            shift 2
            ;;
        --steal)
            STEAL=true
            shift
            ;;
        --allow-dirty)
            ALLOW_DIRTY=true
            shift
            ;;
        --allow-unpushed)
            ALLOW_UNPUSHED=true
            shift
            ;;
        -h|--help)
            echo "Usage: worktree-remove.sh <worktree-path> [--force] [--delete-branch] [--steal] [--allow-dirty] [--allow-unpushed]"
            echo ""
            echo "Safely remove git worktrees. If you're currently inside the worktree"
            echo "being removed, the script automatically changes to the main repository"
            echo "first to prevent breaking your shell session."
            echo ""
            echo "Options:"
            echo "  --force          Pass --force to 'git worktree remove' (the worktree is"
            echo "                   busy). It does NOT override the data-loss refusals below"
            echo "                   - being busy is not the same as being expendable (#899)"
            echo "  --delete-branch  Also delete the associated branch after removal"
            echo "                   (force-deletes a squash-merged branch non-interactively)"
            echo "  --steal          Remove even when another live /flow session claims it"
            echo "                   (issue #597; without it a live claim is a hard stop)"
            echo "  --allow-dirty    Remove even though uncommitted work would be destroyed"
            echo "                   (issue #899; exit 6 without it; implies --force, since"
            echo "                   git worktree remove makes its own separate dirty-tree"
            echo "                   judgment, Nit Store #864)"
            echo "  --allow-unpushed Remove even though commits exist on no remote ref"
            echo "                   (issue #899; exit 7 without it)"
            echo "  --finish-partial-removal"
            echo "                   VERIFY (never remove) a worktree already left half-"
            echo "                   deleted (no .git file). On a pass, PRINTS the rm -rf"
            echo "                   command for a human to run - never runs it. Requires"
            echo "                   --owner-repo AND --allow-dirty - there is no .git left"
            echo "                   to verify the directory is clean. Also needs"
            echo "                   --allow-unpushed, but only if the owner's own refs show"
            echo "                   HEAD is actually unreachable from a remote (#1524)"
            echo "  --owner-repo <path>"
            echo "                   The repo whose own registry must positively list the"
            echo "                   target as prunable. Required by --finish-partial-removal"
            echo ""
            echo "Each refusal has its own override on purpose: one flag that silenced all"
            echo "three would be one flag away from silencing everything."
            echo ""
            echo "Exit codes:"
            echo "  0  removed (or already absent - stale refs pruned); normal path only"
            echo "  1  usage, path, or repository validation error"
            echo "  4  claimed by another live /flow session (#597)"
            echo "  5  in use by a live process (#888, #1032)"
            echo "  6  holds uncommitted work without --allow-dirty (#899)"
            echo "  7  holds commits on no remote ref without --allow-unpushed (#899); for"
            echo "     --finish-partial-removal this is checked via the owner's own refs"
            echo "  8  --delete-branch asked for, but the directory name and the"
            echo "     checked-out branch name different issues (#1032)"
            echo "  9  a path cannot be deleted (parent directory not writable) (#864)"
            echo " 10  --finish-partial-removal/--owner-repo given without the other (#1524)"
            echo " 11  a literal newline in the argument (any invocation), --owner-repo, or"
            echo "     the resolved target (--finish-partial-removal) - refused (#1524)"
            echo " 12  --owner-repo is not a readable git working tree (#1524)"
            echo " 13  --owner-repo's registry does not positively list the path as"
            echo "     prunable (#1524)"
            echo " 14  --finish-partial-removal without --allow-dirty (#1524)"
            echo " 15  --finish-partial-removal: VERIFIED, not removed - printed instead (#1524)."
            echo "     Distinct from 2 on purpose: a failing grep or bash builtin under"
            echo "     set -euo pipefail also exits 2 elsewhere in this script."
            echo ""
            echo "Examples:"
            echo "  worktree-remove.sh /home/user/Projects/nhl-api-issue-42"
            echo "  worktree-remove.sh ../nhl-api-issue-42 --delete-branch"
            echo "  worktree-remove.sh /path/to/half-deleted-wt --finish-partial-removal \\"
            echo "      --owner-repo /path/to/main --allow-dirty --allow-unpushed"
            exit 0
            ;;
        *)
            if [[ -z "$WORKTREE_PATH" ]]; then
                WORKTREE_PATH="$1"
            else
                echo -e "${RED}Error: Unknown argument: $1${NC}" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$WORKTREE_PATH" ]]; then
    echo -e "${RED}Error: Worktree path is required${NC}" >&2
    echo "Usage: worktree-remove.sh <worktree-path> [--force] [--delete-branch] [--steal] [--allow-dirty] [--allow-unpushed]"
    exit 1
fi

# Codex cross-model review (issue #1524, pass 3, HIGH): reject a literal
# newline in the RAW argument for EVERY invocation, before any
# normalization - not only inside --finish-partial-removal. The relative-
# path resolution two blocks below is command substitution wrapped around
# `basename`, and `basename` always appends its OWN trailing newline; when
# the argument's last byte is already a newline, that becomes two
# consecutive trailing newlines, and command substitution strips ALL of
# them. Verified directly: a relative argument "collider" + a literal
# trailing newline normalizes to the newline-free sibling "collider" - the
# SAME hazard --finish-partial-removal's own newline guards exist to close,
# reached through the NORMAL removal path instead, which has no guard of
# its own and would act on whatever that newline-free name happens to name.
# One guard, here, before normalization, closes it for both paths at once.
case "$WORKTREE_PATH" in
    *$'\n'*)
        echo -e "${RED}Error: refusing a path containing a literal newline${NC}" >&2
        exit 11
        ;;
esac

# Same guard, same reason, for --owner-repo (pass-4 supplementary review,
# cnb-orch + Gemini): it feeds its own `git -C "$OWNER_REPO" ...` calls below
# exactly as WORKTREE_PATH feeds the removal/registry calls above, so a
# literal newline in it is refused here too, before anything reads it.
case "$OWNER_REPO" in
    *$'\n'*)
        echo -e "${RED}Error: refusing --owner-repo containing a literal newline${NC}" >&2
        exit 11
        ;;
esac

# --finish-partial-removal and --owner-repo are a PAIR, never one without the
# other (issue #1524): the flag with no named owner would have nothing to
# confirm ownership against, and a bare --owner-repo on the ordinary path
# means nothing at all.
if [[ "$FINISH_PARTIAL_REMOVAL" == true && -z "$OWNER_REPO" ]]; then
    echo -e "${RED}Error: --finish-partial-removal requires --owner-repo${NC}" >&2
    exit 10
fi
if [[ "$FINISH_PARTIAL_REMOVAL" != true && -n "$OWNER_REPO" ]]; then
    echo -e "${RED}Error: --owner-repo is only meaningful with --finish-partial-removal${NC}" >&2
    exit 10
fi

# Resolve to absolute path. REFUSE if the parent cannot be entered, for
# EVERY invocation (pass-4 supplementary review, cnb-orch + Gemini): the old
# single-expression form silently substituted "" for a `cd` failure, so
# WORKTREE_PATH became "/$(basename ...)" - an absolute, filesystem-ROOT
# path unrelated to the argument's actual (missing) parent directory - and
# the script carried on as if that had been the caller's intent all along.
# Splitting the `cd` out and checking its own exit status, rather than
# trusting the combined command substitution's output, is what makes a
# resolution failure visible instead of silently reinterpreted.
if [[ "$WORKTREE_PATH" != /* ]]; then
    WT_DIR_PART="$(dirname "$WORKTREE_PATH")"
    WT_REAL_DIR="$(cd -- "$WT_DIR_PART" 2>/dev/null && pwd)" || {
        echo -e "${RED}Error: could not resolve the directory containing '${WORKTREE_PATH}'${NC}" >&2
        exit 1
    }
    WORKTREE_PATH="$WT_REAL_DIR/$(basename "$WORKTREE_PATH")"
fi

# Normalize path (remove trailing slash)
WORKTREE_PATH="${WORKTREE_PATH%/}"

# Resolved ONCE, early, and used for every later comparison and for the
# actual removal (issue #1524). /proc/<pid>/cwd is fully resolved, so the
# occupancy scan needs this form too - computing it here rather than at its
# first use lets --finish-partial-removal share the same resolution the
# normal path already relied on. `readlink -f` on a path whose final
# component is a symlink resolves to the REAL target, never the link itself -
# load-bearing for --finish-partial-removal, which must never `rm -rf` a
# symlink the caller passed in (see below).
WT_REAL="$(readlink -f "$WORKTREE_PATH" 2>/dev/null || echo "$WORKTREE_PATH")"

# Hoisted here (originally defined just above their own call sites further
# down) so --finish-partial-removal's own branch - which runs much earlier,
# at the "no .git file" check below, before a normal worktree's main
# repository can even be derived - can call them too. Moving a pure function
# definition earlier changes nothing about its later call site; bash just
# needs the definition to have executed before the first call, wherever that
# call is.

# This script plus its ancestors. /flow:auto invokes us from a shell whose cwd
# may still be the worktree, so without this the guard trips over its own caller
# and every removal blocks.
occupancy_self_pids() {
    local pid=$$ depth=0 ppid
    while [[ -n "$pid" && "$pid" != "0" && "$depth" -lt 64 ]]; do
        printf '%s\n' "$pid"
        ppid="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null || true)"
        pid="$ppid"
        depth=$((depth + 1))
    done
}

# Prints "<pid> <comm>" per live process whose cwd is at or under $1.
# Exit 0 = the scan RAN (whether or not it found anything).
# Exit 2 = the scan could NOT run. That must read as "unknown", never as
# "clear": a host that cannot look reporting a clean result is exactly the
# false reassurance this guard exists to remove.
# WORKTREE_REMOVE_PROC_ROOT is a test seam, not a tuning knob: it exists so the
# "cannot scan" branch below can be exercised on a host that has a perfectly good
# /proc. Nothing in normal operation sets it.
PROC_ROOT="${WORKTREE_REMOVE_PROC_ROOT:-/proc}"

occupancy_scan() {
    local wt="$1" entry pid cwd comm
    [[ -r "$PROC_ROOT/self/cwd" ]] || return 2
    local skip_pids
    skip_pids=" $(occupancy_self_pids | tr '\n' ' ') "
    for entry in "$PROC_ROOT"/[0-9]*; do
        if [[ "$entry" == "$PROC_ROOT/[0-9]*" ]]; then
            return 2   # a proc tree exposing no process - we learned nothing
        fi
        pid="${entry##*/}"
        case "$skip_pids" in *" $pid "*) continue ;; esac
        cwd="$(readlink "$entry/cwd" 2>/dev/null)" || continue
        [[ -n "$cwd" ]] || continue
        # Exact path, or a genuine child of it. A bare prefix test would make
        # `<wt>-2` look like it lives inside `<wt>`; on the host where this bug
        # was found `kyle-issue-1142` is a real prefix of
        # `kyle-issue-1142-container-spec-superseded`, so that is not a
        # hypothetical collision.
        if [[ "$cwd" == "$wt" || "${cwd#"$wt"/}" != "$cwd" ]]; then
            comm="$(tr -d '\0' < "$entry/comm" 2>/dev/null || echo '?')"
            printf '%s %s\n' "$pid" "$comm"
        fi
    done
    return 0
}

# "could not verify", never as a clean scan.
#
# The PARENT of the worktree ROOT is checked too: `find` only walks AT OR
# BELOW root, so emptying every descendant still leaves one more removal -
# `rmdir` on the root itself - which needs write+execute on a directory
# outside anything `find` ever saw.
#
# A STICKY-BIT directory (mode +t, like /tmp) restricts unlink/rename of each
# entry inside it to that entry's own owner, the directory's owner, or a
# privileged (root) process - regardless of the directory's own rwx bits
# (issue #1520, follow-up to #1491/Nit Store #864). So a sticky directory
# where the caller has full rwx can still contain a file the caller cannot
# actually delete; the rwx check above cannot see this at all. sticky_dir_is_safe
# is the exemption decision in isolation (no filesystem or subprocess calls),
# and the loop below calls that SAME function - not a parallel reimplementation -
# so a regression in the predicate's body is visible to both the integration-
# level pre-scan tests and the direct unit tests in
# tests/test_worktree_remove_partial.py (cnb-orch review of #1520: a test
# exercising a separately-written copy would stay green while the shipped
# predicate is wrong).
sticky_dir_is_safe() {
    local dir_owner="$1" entry_owner="$2" caller_uid="$3"
    [[ "$caller_uid" == 0 || "$dir_owner" == "$caller_uid" || "$entry_owner" == "$caller_uid" ]]
}

# Whether CALLER_UID can unlink ENTRY out of CONTAINING_DIR, given
# CONTAINING_DIR is sticky. Prints ENTRY and returns 1 (unsafe) when it
# cannot; returns 0 (safe, nothing printed) when it can, including when
# CONTAINING_DIR is not sticky at all - the sticky restriction is the only
# thing this function enforces, so a non-sticky directory is always safe as
# far as this check is concerned, and the caller's OWN rwx check governs it
# instead (undeletable_find's existing per-directory and per-parent checks).
# A failed ownership lookup prints ENTRY too (fail closed, matching the rest
# of this scan): "could not verify" must never read as "clear". Shared by
# undeletable_find's per-directory entry loop and the worktree root's own
# parent (Codex review of #1520: the parent is rwx-checked separately below,
# and sticky-bit coverage must reach it too, not only the descendants `find`
# walks).
sticky_entry_check() {
    local containing_dir="$1" entry="$2" caller_uid="$3" dir_owner entry_owner
    [[ -k "$containing_dir" ]] || return 0
    dir_owner="$(stat -c %u "$containing_dir" 2>/dev/null)" || dir_owner=""
    entry_owner="$(stat -c %u "$entry" 2>/dev/null)" || entry_owner=""
    if [[ -z "$dir_owner" || -z "$entry_owner" ]]; then
        printf '%s\n' "$entry"
        return 1
    fi
    sticky_dir_is_safe "$dir_owner" "$entry_owner" "$caller_uid" && return 0
    printf '%s\n' "$entry"
    return 1
}

undeletable_find() {
    local root="$1" dir rc=0 listing parent caller_uid entries entry
    caller_uid="$(id -u)"
    listing=$(mktemp "${TMPDIR:-/tmp}/worktree-remove-scan.XXXXXX")
    find "$root" -type d -print0 2>/dev/null > "$listing" || rc=$?
    while IFS= read -r -d '' dir; do
        if [[ ! ( -r "$dir" && -w "$dir" && -x "$dir" ) ]]; then
            printf '%s\n' "$dir"
            continue
        fi
        [[ -k "$dir" ]] || continue
        entries=$(mktemp "${TMPDIR:-/tmp}/worktree-remove-scan.XXXXXX")
        if ! find "$dir" -mindepth 1 -maxdepth 1 -print0 2>/dev/null > "$entries"; then
            rc=1
            printf '%s\n' "$dir"
            rm -f "$entries"
            continue
        fi
        while IFS= read -r -d '' entry; do
            sticky_entry_check "$dir" "$entry" "$caller_uid" || true
        done < "$entries"
        rm -f "$entries"
    done < "$listing"
    rm -f "$listing"
    parent="$(dirname "$root")"
    if [[ -w "$parent" && -x "$parent" ]]; then
        sticky_entry_check "$parent" "$root" "$caller_uid" || true
    else
        printf '%s\n' "$parent"
    fi
    return "$rc"
}

# Get current working directory
CWD="$(pwd 2>/dev/null || echo "")"
CWD="${CWD%/}"

# Check if we're inside the worktree being removed
INSIDE_WORKTREE=false
if [[ -n "$CWD" && ( "$CWD" == "$WORKTREE_PATH" || "${CWD#"$WORKTREE_PATH"/}" != "$CWD" ) ]]; then
    INSIDE_WORKTREE=true
fi

# Check if worktree exists
if [[ ! -d "$WORKTREE_PATH" ]]; then
    echo -e "${YELLOW}Warning: Worktree directory does not exist: ${WORKTREE_PATH}${NC}"
    echo "It may have already been removed. Running 'git worktree prune'..."

    # Find the main repo (a directory whose .git is a real directory, not a
    # worktree's .git file). Two layouts to cover:
    #   1. Legacy sibling worktrees:  ../repo-issue-N  (main repo is a sibling)
    #   2. Native worktrees:          .claude/worktrees/<name>  (main repo is an ancestor)
    PRUNE_REPO=""
    # (1) Scan siblings of the worktree path.
    for parent in "$(dirname "$WORKTREE_PATH")"/*; do
        if [[ -d "$parent/.git" ]]; then
            PRUNE_REPO="$parent"
            break
        fi
    done
    # (2) Walk up ancestors (covers .claude/worktrees/<name> nested under the repo).
    if [[ -z "$PRUNE_REPO" ]]; then
        ancestor="$(dirname "$WORKTREE_PATH")"
        while [[ "$ancestor" != "/" && -n "$ancestor" ]]; do
            if [[ -d "$ancestor/.git" ]]; then
                PRUNE_REPO="$ancestor"
                break
            fi
            ancestor="$(dirname "$ancestor")"
        done
    fi
    if [[ -n "$PRUNE_REPO" ]]; then
        git -C "$PRUNE_REPO" worktree prune
        echo -e "${GREEN}Pruned stale worktree references.${NC}"
    else
        echo -e "${YELLOW}Could not locate the main repository to prune; run 'git worktree prune' from it manually.${NC}"
    fi
    exit 0
fi

# Check if it's actually a worktree (has .git file, not directory)
if [[ ! -f "$WORKTREE_PATH/.git" ]]; then
    if [[ "$FINISH_PARTIAL_REMOVAL" != true ]]; then
        echo -e "${RED}Error: ${WORKTREE_PATH} is not a git worktree${NC}" >&2
        echo "(Worktrees have a .git file, not a .git directory)" >&2
        exit 1
    fi

    # --finish-partial-removal (issue #1524): POSITIVE OWNERSHIP ONLY, never
    # discovery. See the header comment above for why - three cross-model
    # review passes on the earlier discovery-based version each found a new
    # variant of the same structural gap, and it was removed entirely rather
    # than patched again.
    #
    # The raw-argument newline guard that used to live here (red case 2) is
    # now global, applied before normalization, before this branch is even
    # reached - see the check near the top of the script, right after
    # "Worktree path is required". Kept here only as this comment, not as a
    # second (unreachable) check: a naive line-based parse of the registry
    # still cannot survive a newline, which is why the NUL-delimited parser
    # below exists independently of that guard.

    if [[ -z "$OWNER_REPO" ]]; then
        # Already validated above; unreachable, but a defensive refusal costs
        # nothing and this function must never fall through silently.
        echo -e "${RED}Error: --owner-repo is required${NC}" >&2
        exit 10
    fi
    if ! git -C "$OWNER_REPO" rev-parse --git-dir >/dev/null 2>&1; then
        echo -e "${RED}Error: --owner-repo '${OWNER_REPO}' is not a readable git working tree${NC}" >&2
        exit 12
    fi

    # Codex cross-model review (issue #1524, pass 2, HIGH): the shared WT_REAL
    # above is plain command substitution, which strips ALL trailing newlines
    # from its OWN captured output - so a pass-1 fix that checked "$WT_REAL"
    # for an embedded newline could never see one in the trailing position,
    # because bash had already removed it before the check ran. Verified
    # directly: a symlink to a directory named "target\n" resolves through
    # that form to WT_REAL with no trailing \n at all.
    #
    # Resolved AGAIN here, robustly, for THIS branch only (never touching the
    # shared WT_REAL the normal path above already relies on). Capture with a
    # non-newline sentinel appended in the SAME command substitution, so
    # nothing trailing gets stripped; then peel the sentinel and exactly the
    # ONE newline `readlink -f` itself always appends as its own line
    # terminator - whatever newline remains after that is part of the real
    # resolved path, not readlink's formatting. A readlink FAILURE is a hard
    # refusal: never fall back to the raw, unresolved argument the way the
    # shared WT_REAL computation does for the normal path.
    if ! readlink -f "$WORKTREE_PATH" >/dev/null 2>&1; then
        echo -e "${RED}Error: could not resolve ${WORKTREE_PATH} to a real path${NC}" >&2
        exit 12
    fi
    FP_WT_REAL="$(readlink -f "$WORKTREE_PATH"; printf 'x')"
    FP_WT_REAL="${FP_WT_REAL%x}"
    FP_WT_REAL="${FP_WT_REAL%$'\n'}"
    if [[ -z "$FP_WT_REAL" ]]; then
        echo -e "${RED}Error: could not resolve ${WORKTREE_PATH} to a real path${NC}" >&2
        exit 12
    fi

    # The newline check above inspects WORKTREE_PATH, the raw argument -
    # check the robustly-resolved FP_WT_REAL too, which is what actually gets
    # compared against the registry and removed.
    case "$FP_WT_REAL" in
        *$'\n'*)
            echo -e "${RED}Error: refusing a resolved path containing a literal newline${NC}" >&2
            exit 11
            ;;
    esac

    # Parse `git worktree list --porcelain -z` field by field, NUL-delimited -
    # never sed/grep/line-based. Measured (issue #1524): each record ends with
    # an EMPTY field (two consecutive NULs), including the last. A record
    # matches only when BOTH its `worktree <path>` field equals FP_WT_REAL
    # EXACTLY and the SAME record carries git's own `prunable` attribute line -
    # which git emits precisely when a worktree's gitdir file points at a
    # location that no longer exists (measured directly: a worktree with its
    # own .git file removed gets `prunable gitdir file points to non-existent
    # location`; the identical state under `git worktree lock` gets `locked
    # <reason>` and NO prunable line at all, so a locked half-deleted worktree
    # is refused by this check with no extra code). A read failure - the
    # porcelain call itself fails - is a REFUSAL, never a silent "proceed
    # because nothing said no". The matching record's HEAD sha is also
    # captured (issue #1524, pass 2 HIGH), so the unpushed-commit check below
    # can ask the owner's own objects/remote refs about it.
    PORCELAIN_FILE=$(mktemp "${TMPDIR:-/tmp}/worktree-remove-porcelain.XXXXXX") || {
        echo -e "${RED}Error: could not create a temp file to read the owner's worktree registry${NC}" >&2
        exit 13
    }
    if ! git -C "$OWNER_REPO" worktree list --porcelain -z > "$PORCELAIN_FILE" 2>/dev/null; then
        rm -f "$PORCELAIN_FILE"
        echo -e "${RED}Error: could not read '${OWNER_REPO}' worktree registry${NC}" >&2
        exit 13
    fi
    RECORD_PATH=""
    RECORD_HEAD=""
    RECORD_PRUNABLE=false
    OWNER_CONFIRMS=false
    MATCHED_HEAD=""
    while IFS= read -r -d '' PORCELAIN_FIELD; do
        if [[ -z "$PORCELAIN_FIELD" ]]; then
            if [[ "$RECORD_PATH" == "$FP_WT_REAL" && "$RECORD_PRUNABLE" == true ]]; then
                OWNER_CONFIRMS=true
                MATCHED_HEAD="$RECORD_HEAD"
            fi
            RECORD_PATH=""
            RECORD_HEAD=""
            RECORD_PRUNABLE=false
            continue
        fi
        case "$PORCELAIN_FIELD" in
            "worktree "*) RECORD_PATH="${PORCELAIN_FIELD#worktree }" ;;
            "HEAD "*) RECORD_HEAD="${PORCELAIN_FIELD#HEAD }" ;;
            "prunable"|"prunable "*) RECORD_PRUNABLE=true ;;
        esac
    done < "$PORCELAIN_FILE"
    rm -f "$PORCELAIN_FILE"

    if [[ "$OWNER_CONFIRMS" != true ]]; then
        echo -e "${RED}Error: '${OWNER_REPO}' does not positively list ${FP_WT_REAL} as prunable${NC}" >&2
        echo "  Refusing: this script never deletes on the strength of a repo NOT" >&2
        echo "  naming the path - only on the strength of one naming it, as prunable." >&2
        echo "  Pass the correct --owner-repo, or check the path with:" >&2
        echo "    git -C '${OWNER_REPO}' worktree list --porcelain" >&2
        exit 13
    fi

    echo "WORKTREE_REMOVE_FINISH_PARTIAL: confirmed by ${OWNER_REPO}" >&2

    # Codex cross-model review (issue #1524, pass 1, HIGH): the ORIGINAL
    # version of this branch ran no dirty-tree check at all, reasoning that
    # `git status` needs the worktree's own .git, which is already gone -
    # "nothing left to check". That reasoning proved too much: removing
    # `.git` does not remove the FILES. A worktree with real uncommitted
    # edits or untracked work sitting in it is still full of exactly that
    # content, and this branch would delete it unconditionally - the state
    # cannot be verified clean, which is the opposite of permission to treat
    # it as clean. --allow-dirty is now REQUIRED for --finish-partial-removal,
    # not merely honoured: there is no `git status` to ask, so the caller
    # must affirmatively accept that whatever is on disk may be destroyed,
    # exactly as the explicit-override convention above requires for every
    # other data-loss path. Checked FIRST, same order as the normal path
    # below (dirty, then unpushed).
    if [[ "$ALLOW_DIRTY" != true ]]; then
        echo -e "${RED}Error: --finish-partial-removal cannot verify this path is clean${NC}" >&2
        echo "  There is no .git file left to ask - the directory may still hold" >&2
        echo "  uncommitted or untracked work. Pass --allow-dirty to confirm you accept" >&2
        echo "  that whatever is on disk may be destroyed." >&2
        exit 14
    fi

    # Codex cross-model review (issue #1524, pass 2, HIGH): unlike the dirty-
    # tree check above, unpushed commits ARE verifiable here, because the
    # owner's own objects and remote-tracking refs are intact even though the
    # worktree's own .git is gone - the matched porcelain record's HEAD sha,
    # captured above, is exactly the commit (or ancestor chain) that would be
    # lost. Reachable from ANY remote-tracking ref in the owner means safe;
    # unreachable, or the check itself failing to run, both mean refuse -
    # "unknown" is not "pushed", same as every other read failure in this
    # branch. #899's own override (--allow-unpushed) applies, same message
    # shape as the normal path's equivalent refusal.
    if [[ "$ALLOW_UNPUSHED" != true ]]; then
        if [[ -z "$MATCHED_HEAD" ]]; then
            echo -e "${RED}Error: could not determine the worktree's HEAD commit to check${NC}" >&2
            echo "  whether it is pushed; refusing rather than assuming it is." >&2
            exit 7
        fi
        FP_REMOTE_CONTAINS_RC=0
        FP_REMOTE_CONTAINS="$(git -C "$OWNER_REPO" branch -r --contains "$MATCHED_HEAD" 2>/dev/null)" \
            || FP_REMOTE_CONTAINS_RC=$?
        if [[ "$FP_REMOTE_CONTAINS_RC" -ne 0 || -z "$FP_REMOTE_CONTAINS" ]]; then
            echo "WORKTREE_REMOVE_UNPUSHED: refused" >&2
            echo -e "${RED}Error: refusing to remove a worktree holding commits that are on no remote${NC}" >&2
            echo "" >&2
            echo "  HEAD: $MATCHED_HEAD" >&2
            echo "  These commits exist nowhere else (issue #899). Push the branch, or pass" >&2
            echo "  --allow-unpushed if you are certain the commits are unwanted. A failed" >&2
            echo "  check of the owner's remote refs also refuses - unknown is not pushed." >&2
            exit 7
        fi
        echo "WORKTREE_REMOVE_UNPUSHED: pushed" >&2
    fi

    # Same occupancy and pre-scan guards as the normal path, run against the
    # resolved path (issue #1524).
    #
    # FP_OCC_UNKNOWN (pass-4 supplementary review, cnb-orch + Gemini): an
    # unreadable /proc still PROCEEDS here, same as the normal path - but
    # unlike the normal path, this branch's whole output IS a printed
    # command a human may paste and run without re-reading this script's
    # stderr. So the same "could not verify" fact is ALSO surfaced on stdout,
    # directly above the printed `rm -rf`, where it cannot be missed.
    FP_OCC_UNKNOWN=false
    if [[ "$STEAL" != true ]]; then
        FP_OCC_RC=0
        FP_OCC_OUT="$(occupancy_scan "$FP_WT_REAL")" || FP_OCC_RC=$?
        if [[ "$FP_OCC_RC" -eq 2 ]]; then
            FP_OCC_UNKNOWN=true
            echo "WORKTREE_REMOVE_OCCUPANCY: unknown" >&2
            echo -e "${YELLOW}Note: no readable /proc - could not check whether a live process is using this path.${NC}" >&2
        elif [[ -n "$FP_OCC_OUT" ]]; then
            echo "WORKTREE_REMOVE_OCCUPANCY: occupied" >&2
            echo -e "${RED}Error: refusing to remove a path that is in use by a live process${NC}" >&2
            echo "" >&2
            echo "  Path: $FP_WT_REAL" >&2
            echo "  Live processes with their working directory inside it:" >&2
            printf '    %s\n' "$FP_OCC_OUT" >&2
            echo "" >&2
            echo "  --force does not override this; wait for that session, or pass --steal" >&2
            echo "  if you are certain those processes can be killed." >&2
            exit 5
        fi
    fi

    FP_PRE_SCAN_RC=0
    FP_PRE_UNDELETABLE="$(undeletable_find "$FP_WT_REAL")" || FP_PRE_SCAN_RC=$?
    if [[ "$FP_PRE_SCAN_RC" -ne 0 ]]; then
        echo "WORKTREE_REMOVE_PRESCAN: unknown" >&2
        echo -e "${RED}Error: the permission scan itself failed - this is not the same as clean${NC}" >&2
        exit 9
    fi
    if [[ -n "$FP_PRE_UNDELETABLE" ]]; then
        echo "WORKTREE_REMOVE_PRESCAN: undeletable" >&2
        echo -e "${RED}Error: refusing to remove - some paths cannot be deleted${NC}" >&2
        printf '    %s\n' "$FP_PRE_UNDELETABLE" >&2
        exit 9
    fi
    echo "WORKTREE_REMOVE_PRESCAN: clear" >&2

    # VERIFY AND PRINT, NEVER REMOVE AUTOMATICALLY (issue #1524, owner
    # decision after a pass-3 HIGH: three review passes each found a real
    # path-handling defect in this branch - a newline guard that checked the
    # wrong value, a missing dirty/unpushed requirement, a readlink
    # trailing-newline loss, and finally a SHARED normalization step that
    # could silently swap the target before any of this branch's own guards
    # ever ran. That is the three-pass ceiling, so this ships as verification
    # only: everything above (positive ownership, occupancy, the undeletable
    # pre-scan, dirty, unpushed) still runs and still refuses on exactly the
    # same conditions - what changes is that a PASS prints the exact command
    # for a human to run, rather than running it. `printf %q` quotes the path
    # so the printed line is safe to copy-paste even if it contains shell
    # metacharacters this review process has not had cause to think about.
    #
    # `worktree prune` is deliberately NOT run or printed as a command here:
    # it prunes every eligible stale entry in the OWNER's whole registry
    # (pass 3, MEDIUM), not just the one target this branch verified - a
    # second, unrelated stale worktree could lose its registration with none
    # of the checks above having looked at it. A `--dry-run --verbose` hint
    # is printed instead, so the human can see exactly what pruning would
    # drop before deciding to run it themselves.
    echo "WORKTREE_REMOVE_FINISH_PARTIAL_VERIFIED: ${FP_WT_REAL}" >&2
    echo -e "${GREEN}Verified - this path is confirmed prunable, clean per --allow-dirty/--allow-unpushed, unoccupied, and deletable. Not removed.${NC}"
    # If occupancy could not be checked (FP_OCC_UNKNOWN), say so directly
    # above the rm line - on stdout, in the same output a human copies the
    # command from - rather than only on stderr above (pass-4 supplementary
    # review, cnb-orch + Gemini).
    if [[ "$FP_OCC_UNKNOWN" == true ]]; then
        echo "# WARNING: could not check for live processes using this path (no readable /proc)"
    fi
    printf 'rm -rf -- %q\n' "$FP_WT_REAL"
    # Printed as a COMMENT (leading '#'), not a bare sentence (pass-4
    # supplementary review): "then review: git -C ..." starts with a shell
    # keyword-free word but is still not valid shell on its own line, so a
    # human who copies both printed lines into a shell at once hits a syntax
    # error on this one. As a comment it is always safe to paste alongside
    # the rm line above, read or ignored at the human's discretion.
    printf '# then review: git -C %q worktree prune --dry-run --verbose\n' "$OWNER_REPO"

    if [[ -L "$WORKTREE_PATH" ]]; then
        echo -e "${YELLOW}Note: ${WORKTREE_PATH} is a symlink pointing at this target.${NC}" >&2
        echo -e "${YELLOW}Running the rm above will leave it dangling; it is not part of the${NC}" >&2
        echo -e "${YELLOW}worktree and is never removed by this tool.${NC}" >&2
    fi

    # Exit code is distinct from 0 (removed) AND from a plain 2 (pass-4
    # supplementary review): under `set -euo pipefail`, a failing `grep` or a
    # bash builtin misuse anywhere in this script can itself surface as exit
    # 2, and that must never be misread as "verified". 15 is otherwise unused
    # in this script's exit-code table.
    exit 15
fi

# Get the main repository path from the worktree's .git file
MAIN_REPO=$(sed 's/gitdir: //' "$WORKTREE_PATH/.git" | sed 's|/.git/worktrees/.*||')

if [[ ! -d "$MAIN_REPO/.git" ]]; then
    echo -e "${RED}Error: Could not find main repository${NC}" >&2
    exit 1
fi

# If we're inside the worktree, cd to main repo first
if [[ "$INSIDE_WORKTREE" == true ]]; then
    echo -e "${YELLOW}Currently inside worktree being removed.${NC}"
    echo -e "${BLUE}Changing to main repository: ${MAIN_REPO}${NC}"
    cd "$MAIN_REPO" || {
        echo -e "${RED}Error: Failed to change to main repository${NC}" >&2
        exit 1
    }
fi

# Get the branch name before removing
BRANCH_NAME=$(git -C "$WORKTREE_PATH" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

# --- Attribution: the BRANCH says whose work this is, never the path (#1032) --
# A worktree directory is named after the issue it was created for, but the name
# is just a string and nothing keeps it in step with what is checked out inside.
# Observed on this host: a directory named `...-issue-971-...` (CLOSED, PR #1004
# merged) holding the branch `issue-980-lexicon-quoted-token` (OPEN). Anything
# deciding "safe to delete" from the directory name would have read "closed and
# merged, safe" and destroyed an open lane's checkout. It survived only because
# #980 happened to have no commits of its own yet.
#
# So: derive the issue from BOTH, report which one is authoritative, and refuse
# the one operation whose blast radius reaches beyond this directory.
#
# Matching is on the issue NUMBER alone, never the slug. A branch legitimately
# keeps an older title's slug while the issue is renamed (#793), so comparing
# full names would fire on the ordinary case - and a guard that fires on the
# normal case is one everybody learns to pass with the override flag.
ATTRIBUTION_MISMATCH=false
issue_of() {  # issue_of <string> -> the N in the FIRST `issue-<N>` segment
    # FIRST, not last. A greedy `.*issue-\([0-9]*\)` takes the LAST match, and
    # slugs quote other issues all the time: branch `issue-980-fix-issue-971`
    # then parses as 971, agrees with directory `repo-issue-971-old`, and the
    # guard waves through exactly the deletion it exists to stop. It failed the
    # other way too - `issue-42-fix-issue-99` read as 99 and disagreed with its
    # own directory. Both were found by the counter-model review of this change.
    # The issue-anchored name puts the owning issue FIRST in both spellings:
    # `issue-<N>-<slug>` for a branch, `<repo>-issue-<N>-<slug>` for a
    # directory. Requiring a digit after `issue-` keeps a repo named e.g.
    # `my-issue-tracker` from matching its own name.
    # `|| true` is load-bearing: this script runs under `set -euo pipefail`, so
    # a grep that matches NOTHING - the ordinary case for a worktree whose name
    # encodes no issue - fails the pipeline and aborts the whole run. "No issue
    # in this name" is an answer, not an error.
    printf '%s' "$1" | grep -o 'issue-[0-9][0-9]*' | head -1 | sed 's/^issue-//' || true
}
# Strip the repository prefix before parsing the DIRECTORY (#1032, second
# counter-model pass). Worktree directories are `<repo>-<branch>` by
# construction, so a repository whose own NAME contains `issue-<N>` puts that
# number ahead of the branch's: for repo `tool-issue-971`, the perfectly
# ordinary directory `tool-issue-971-issue-980-fix` parses as 971 and both
# failure directions return - a false refusal against branch `issue-980-fix`,
# and a false `agree` against `issue-971-old` that permits deleting the wrong
# branch. Taking the FIRST match fixed slugs quoting other issues; it could not
# fix this, because here the foreign number genuinely comes first.
#
# When the basename does not carry the prefix (a hand-made checkout), the strip
# is a no-op and parsing falls back to the whole name, exactly as before.
DIR_BASENAME="$(basename "$WORKTREE_PATH")"
REPO_BASENAME="$(basename "$MAIN_REPO")"
DIRNAME_ISSUE="$(issue_of "${DIR_BASENAME#"$REPO_BASENAME"-}")"
BRANCH_ISSUE="$(issue_of "$BRANCH_NAME")"

if [[ -z "$DIRNAME_ISSUE" || -z "$BRANCH_ISSUE" ]]; then
    # A path under FLOW_WORKTREE_BASE, a hand-made checkout, or a detached HEAD.
    # There is nothing to disagree about, and an unkeyed name is NOT a mismatch:
    # reporting it as one would make the refusal fire on every non-flow worktree.
    echo "WORKTREE_REMOVE_ATTRIBUTION: branch=${BRANCH_NAME:--} dirname-unkeyed"
elif [[ "$DIRNAME_ISSUE" == "$BRANCH_ISSUE" ]]; then
    echo "WORKTREE_REMOVE_ATTRIBUTION: branch=${BRANCH_NAME} issue=${BRANCH_ISSUE} agree"
else
    echo "WORKTREE_REMOVE_ATTRIBUTION: branch=${BRANCH_NAME} issue=${BRANCH_ISSUE} dirname-issue=${DIRNAME_ISSUE} DISAGREE"
    echo -e "${YELLOW}Warning: this worktree's directory name does not match the work inside it.${NC}" >&2
    echo "" >&2
    echo "  Directory: ${DIR_BASENAME}  -> says issue #${DIRNAME_ISSUE}" >&2
    echo "  Branch:    ${BRANCH_NAME}  -> IS issue #${BRANCH_ISSUE}" >&2
    echo "" >&2
    echo "  The branch is authoritative: this checkout holds issue #${BRANCH_ISSUE}'s work" >&2
    echo "  (issue #1032). Anything that judged this tree by its directory name has" >&2
    echo "  been reasoning about the wrong issue's state." >&2
    ATTRIBUTION_MISMATCH=true
fi

# --- Cross-session claim check (issue #597) ----------------------------------
# Another LIVE /flow session may be driving this checkout right now. Removing it
# out from under that session is the silent-data-loss failure this guard exists
# for, so a live parseable claim is a hard stop. A claim owned by THIS session,
# or left behind by a session that has since died, is simply released first. An
# unparseable lock identifies no owner and falls through to the independent
# occupancy and work checks below.
#
# Fail-open in both directions: a missing helper, an unreadable lock, or a git
# too old to report one leaves the previous behavior exactly as it was.
SELF_SCRIPT_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")")"
CLAIM_OWNED_BY_US=false
CLAIM_HELPER=""
for cand in "$SELF_SCRIPT_DIR/flow-worktree-claim.sh" "$HOME/.claude/scripts/flow-worktree-claim.sh"; do
    if [[ -f "$cand" ]]; then
        CLAIM_HELPER="$cand"
        break
    fi
done

if [[ -n "$CLAIM_HELPER" ]]; then
    CLAIM_OUT=$(bash "$CLAIM_HELPER" check "$WORKTREE_PATH" 2>/dev/null || true)
    CLAIM_STATE=$(printf '%s\n' "$CLAIM_OUT" | sed -n 's/^FLOW_CLAIM: //p' | tail -1)
    CLAIM_PID=$(printf '%s\n' "$CLAIM_OUT" | sed -n 's/^FLOW_CLAIM_OWNER_PID=//p' | tail -1)
    CLAIM_SESSION=$(printf '%s\n' "$CLAIM_OUT" | sed -n 's/^FLOW_CLAIM_OWNER_SESSION=//p' | tail -1)
    CLAIM_ISSUE=$(printf '%s\n' "$CLAIM_OUT" | sed -n 's/^FLOW_CLAIM_ISSUE=//p' | tail -1)
    # How liveness was decided, not just what it decided (issue #1032). "the
    # owner exited" and "that pid belongs to somebody else now" are different
    # facts, and only the second explains why a claim that looked live is gone.
    CLAIM_WITNESS=$(printf '%s\n' "$CLAIM_OUT" | sed -n 's/^FLOW_CLAIM_OWNER_WITNESS=//p' | tail -1)
    CLAIM_STALE_REASON=$(printf '%s\n' "$CLAIM_OUT" | sed -n 's/^FLOW_CLAIM_STALE_REASON=//p' | tail -1)

    case "${CLAIM_STATE:-unknown}" in
        held)
            if [[ "$STEAL" != true ]]; then
                echo -e "${RED}Error: refusing to remove a worktree claimed by another session${NC}" >&2
                echo "" >&2
                echo "  Worktree: $WORKTREE_PATH" >&2
                echo "  Claim:    ${CLAIM_STATE} (issue #${CLAIM_ISSUE:--}, pid ${CLAIM_PID:--}, session ${CLAIM_SESSION:--}, identity ${CLAIM_WITNESS:--})" >&2
                echo "" >&2
                echo "  Another /flow session is driving this checkout. Removing it would destroy" >&2
                echo "  its uncommitted work - the failure this claim exists to prevent (issue #597)." >&2
                echo "  Wait for that session to finish, or pass --steal if you are certain it is gone." >&2
                exit 4
            fi
            echo -e "${YELLOW}Warning: --steal given; removing a worktree claimed by pid ${CLAIM_PID:--}.${NC}" >&2
            bash "$CLAIM_HELPER" release "$WORKTREE_PATH" --force >/dev/null 2>&1 || true
            ;;
        foreign)
            echo -e "${YELLOW}Warning: this worktree carries a lock that does not identify a session${NC}" >&2
            echo "" >&2
            echo "  Worktree: $WORKTREE_PATH" >&2
            echo "  Claim:    unparseable lock (identifies no issue, pid, or session)" >&2
            echo "" >&2
            echo "  This is not evidence the worktree is idle OR in use (issue #1032)." >&2
            echo "  Checking live occupancy and uncommitted/unpushed work independently" >&2
            echo "  before deciding." >&2
            ;;
        self)
            # Ours - drop the lock so the removal below can proceed.
            bash "$CLAIM_HELPER" release "$WORKTREE_PATH" >/dev/null 2>&1 || true
            CLAIM_OWNED_BY_US=true
            ;;
        stale)
            # The claiming session is gone. Drop its lock, but do NOT treat that
            # as proof the checkout is idle: a test run or server it started can
            # outlive it, reparented and still writing here (issue #888).
            case "$CLAIM_STALE_REASON" in
                recycled-pid)
                    echo -e "${YELLOW}Note: the claim's pid ${CLAIM_PID:--} exists but is a DIFFERENT process${NC}" >&2
                    echo "  (its start-time does not match the one recorded in the claim), so the" >&2
                    echo "  owning session is gone and its pid was recycled. Before issue #1032" >&2
                    echo "  this read as a LIVE owner and the worktree was unremovable without" >&2
                    echo "  --steal." >&2
                    ;;
                aged-out-unverified | aged-out-remote-host)
                    # Say what expired. The process may well still be running -
                    # claiming it is gone would assert something never checked.
                    echo -e "${YELLOW}Note: this claim EXPIRED rather than its owner exiting${NC}" >&2
                    echo "  (reason: ${CLAIM_STALE_REASON}). The recorded owner could not be" >&2
                    echo "  identified, so the age bound released it. The occupancy check below" >&2
                    echo "  is what actually establishes whether anything is working here." >&2
                    ;;
            esac
            bash "$CLAIM_HELPER" release "$WORKTREE_PATH" >/dev/null 2>&1 || true
            ;;
        *)
            # free | unsupported | unknown | empty. NONE of these is a claim, and
            # none is evidence of an idle checkout - `free` is simply what any
            # worktree created before claiming existed, or outside the /flow
            # lane, reports. The old code fell through here silently and removed
            # it; the occupancy check below is what now stands in that gap.
            :
            ;;
    esac
fi

# --- Live-occupancy check (issue #888) ---------------------------------------
# The claim above protects a worktree only where one was actually staked. Four
# states leave it unprotected - `free` (no claim ever filed), `foreign` (a lock
# that identifies no /flow owner), `unsupported` (git too old to lock) and
# `unknown` (the lock could not be read) - and an unclaimed worktree is
# indistinguishable from an idle one, so it was removed.
#
# That is how a LIVE session loses unsaved work. On 2026-09-13 a session sitting
# in `flow-finish-gate` held a 21KB staged file in a worktree reporting
# CLAIM=free; the only thing between it and deletion was the #503 mtime
# heuristic, whose 30-minute window that session had already outlived by being
# in a long test run. Both guards read "clear" on a checkout that was plainly
# occupied.
#
# So when the claim did not positively name THIS session as owner, ask a second
# question no time window can blind: is a live process sitting in it? A process
# whose cwd would be unlinked may create unreachable work immediately after a
# clean scan, so an occupied worktree is not ours to delete. Unlike the
# dirty-tree check below, --force does NOT suppress this one: --force is
# precisely what every /flow:auto Step 7 passes, so a guard it silences is a
# guard that never fires where the damage happens. --steal remains the
# deliberate override.
#
# WT_REAL, occupancy_self_pids, PROC_ROOT and occupancy_scan are all defined
# earlier now (issue #1524), so --finish-partial-removal's own branch can use
# them too - see the comment there.

if [[ "$CLAIM_OWNED_BY_US" != true && "$STEAL" != true ]]; then
    OCC_RC=0
    OCC_OUT="$(occupancy_scan "$WT_REAL")" || OCC_RC=$?
    if [[ "$OCC_RC" -eq 2 ]]; then
        # Say so rather than implying a clean result.
        echo "WORKTREE_REMOVE_OCCUPANCY: unknown" >&2
        echo -e "${YELLOW}Note: no readable /proc - could not check whether a live process is using this worktree.${NC}" >&2
    elif [[ -n "$OCC_OUT" ]]; then
        OCC_DIRTY="$(git -C "$WORKTREE_PATH" status --porcelain 2>/dev/null || echo "")"
        if [[ -n "$OCC_DIRTY" ]]; then
            echo "WORKTREE_REMOVE_OCCUPANCY: occupied-dirty" >&2
            echo -e "${RED}Error: refusing to remove a worktree that is in use and holds uncommitted work${NC}" >&2
            echo "" >&2
            echo "  Worktree: $WORKTREE_PATH" >&2
            echo "  Claim:    ${CLAIM_STATE:-none} (no claim naming this session)" >&2
            echo "" >&2
            echo "  Live processes with their working directory inside it:" >&2
            printf '    %s\n' "$OCC_OUT" >&2
            echo "" >&2
            echo "  Uncommitted work that removal would destroy:" >&2
            printf '    %s\n' "$OCC_DIRTY" >&2
            echo "" >&2
            echo "  Another session is driving this checkout without having staked a claim" >&2
            echo "  (issue #888). --force does not override this; wait for that session, or" >&2
            echo "  pass --steal if you are certain those processes can be killed." >&2
            exit 5
        fi
        echo "WORKTREE_REMOVE_OCCUPANCY: occupied-clean" >&2
        echo -e "${RED}Error: refusing to remove a clean worktree that is in use by a live process${NC}" >&2
        echo "" >&2
        echo "  Worktree: $WORKTREE_PATH" >&2
        echo "  Claim:    ${CLAIM_STATE:-none} (no claim naming this session)" >&2
        echo "" >&2
        echo "  Live processes with their working directory inside it:" >&2
        printf '    %s\n' "$OCC_OUT" >&2
        echo "" >&2
        echo "  There is no uncommitted work right now, but a live process could create" >&2
        echo "  work after this check. Removing the worktree would unlink that process's" >&2
        echo "  working directory (issue #1032). --force does not override this; wait for" >&2
        echo "  the process to finish, or pass --steal if you are certain it can be killed." >&2
        exit 5
    else
        echo "WORKTREE_REMOVE_OCCUPANCY: clear" >&2
    fi
fi

# --- Uncommitted-work check (issue #899) -------------------------------------
# This used to be gated on `--force` being ABSENT, which meant --force deleted
# uncommitted work on any worktree with no live process. "Idle" is not
# "abandoned": an agent session between tool calls has NO process running while
# its worktree may hold hours of work, and #888's observed case was a STAGED
# 21KB spec file. #889's occupancy guard catches that only while a process is
# live, so --force plus an idle worktree was an unguarded delete.
#
# --force no longer suppresses it. --allow-dirty does, and nothing else:
# `--force` means "the worktree is busy, make git remove it anyway", which is a
# different assertion from "I accept losing the contents".
#
# ANY porcelain entry counts, including untracked files - deliberately, and
# measured rather than assumed. The concern was that ignored build artifacts
# would make this fire constantly on the ordinary post-merge path and train
# people to pass the override reflexively, destroying the guard exactly as #888
# destroyed the last one. Measured on three worktrees that had each run the full
# suite and built a .venv: `.venv` present, 41 `__pycache__` directories,
# `status --porcelain --ignored` showing 15 entries - and `status --porcelain`
# reporting ZERO. .gitignore already suppresses them, so they never reach this
# check and the false-refusal surface is not there.
#
# Untracked-but-not-ignored was also zero, which is what decides the simple form
# over splitting tracked from untracked: an untracked file that .gitignore does
# NOT cover is a source file somebody created and never staged, which is exactly
# the work an agent produces and exactly what a split would have deleted.
if [[ "$ALLOW_DIRTY" != true ]]; then
    CHANGES=$(git -C "$WORKTREE_PATH" status --porcelain 2>/dev/null || echo "")
    if [[ -n "$CHANGES" ]]; then
        echo "WORKTREE_REMOVE_DIRTY: refused" >&2
        echo -e "${RED}Error: refusing to remove a worktree that holds uncommitted work${NC}" >&2
        echo "" >&2
        git -C "$WORKTREE_PATH" status --short >&2
        echo "" >&2
        echo "  Removing it would destroy the above (issue #899). --force does NOT" >&2
        echo "  override this: it says the worktree is busy, not that its contents are" >&2
        echo "  expendable. Commit or stash first, or pass --allow-dirty if you are" >&2
        echo "  certain none of it is wanted." >&2
        exit 6
    fi
    # Reached only when the check RAN and found nothing (issue #916).
    echo "WORKTREE_REMOVE_DIRTY: clean" >&2
else
    # A check that was SKIPPED must not print the word a check that PASSED
    # prints. This echo used to sit outside the guard, so `--allow-dirty` on a
    # tree holding uncommitted work announced `clean` - and the tree was never
    # measured. Same membership floor the UNPUSHED states already observe:
    # never-checked and checked-and-empty are different facts.
    echo "WORKTREE_REMOVE_DIRTY: overridden" >&2
    # `--allow-dirty` clears only THIS helper's own refusal (#899); `git
    # worktree remove` makes its OWN, separate judgment about a dirty tree and
    # still refuses without `--force` (exit 128, undocumented) - so without
    # this, `--allow-dirty` alone silenced nothing and the removal failed
    # anyway (Nit Store #864, comment 6155393127). The two flags are asking the
    # same question of two different gatekeepers; granting one grants the
    # other, rather than making the caller discover and pass both.
    FORCE="--force"
fi

# Did the merge helper record THIS commit as landed? (issue #916)
#
# Accepts ONLY an exact match against HEAD. The record is written by
# gh-pr-merge.sh inside its MERGED block, so an OID that appears here is one
# that genuinely landed; requiring equality is what makes a stale record
# harmless rather than dangerous. `git branch -D` clears the record, but
# `git update-ref -d` does not (measured), so records CAN survive their branch -
# the equality check, not the cleanup, is the guarantee.
#
# Deliberately offline. A network lookup here would put a call that can fail on
# the refusal path of a helper whose job is DELETING, and the sweep one level up
# already performs exactly that lookup.
landed_record_matches() {
    local recorded head
    recorded=$(git -C "$WORKTREE_PATH" config --get "branch.${BRANCH_NAME}.cpp-merged-head" 2>/dev/null) || return 1
    [[ -n "$recorded" ]] || return 1
    head=$(git -C "$WORKTREE_PATH" rev-parse HEAD 2>/dev/null) || return 1
    [[ -n "$head" && "$recorded" == "$head" ]]
}

# --- Unpushed-commits check (issue #899) -------------------------------------
# Nothing in this helper looked at commits at all. `git status --porcelain`
# reports CLEAN for a tree whose commits were never pushed, so the occupancy
# guard saw occupied-clean and proceeded; with --delete-branch the ref then went
# too and the commits survived only via `git fsck --lost-found` until gc.
#
# NOT `git log @{u}..`, which the issue suggested and which cannot work here.
# Measured - it fails IDENTICALLY in the two cases it would have to separate:
#
#   merged, remote branch pruned (THE ORDINARY PATH)  fatal: no upstream configured
#   committed, never pushed (THE DATA-LOSS CASE)      fatal: no upstream configured
#
# So anything built on it must refuse both, breaking every ordinary removal, or
# allow both, leaving the gap where it was. `gh pr merge --delete-branch` makes
# the no-upstream state the NORMAL one, which is why this is not an edge case.
#
# `HEAD --not --remotes` asks the question that actually matters - are there
# commits here that exist on no remote ref - and separates them: empty for a
# merged branch (its commits are reachable from origin/main) and non-empty for
# work that was never pushed. It is git-native, offline, and needs no PR lookup,
# which the sweep's second mechanism does.
#
# Also measured against a STALE origin/main, the ordering most likely to produce
# a false refusal: a server-side merge this clone has not fetched still reports
# empty, because the local origin/<branch> ref covers HEAD before a prune and
# origin/main covers it after. Safe in both directions.
if [[ "$ALLOW_UNPUSHED" != true ]]; then
    # A repo with NO remote-tracking refs at all is the trap here, and it is not
    # hypothetical - `git init` with no remote is a legitimate repo and is what
    # every fixture in this suite builds. `HEAD --not --remotes` reports EVERY
    # commit there, because there is no remote for anything to be on, so a naive
    # reading refuses every removal in any local-only repo. "This repo has no
    # remotes" and "these commits are on no remote" are different facts and only
    # the second is data loss; conflating them is the same membership-floor
    # mistake as reading a blank state as a clean one.
    if [[ -z "$(git -C "$WORKTREE_PATH" for-each-ref --count=1 refs/remotes 2>/dev/null)" ]]; then
        echo "WORKTREE_REMOVE_UNPUSHED: unknown" >&2
        echo -e "${YELLOW}Note: no remote-tracking refs in this repository - cannot tell whether commits are pushed.${NC}" >&2
    else
        UNPUSHED_RC=0
        UNPUSHED=$(git -C "$WORKTREE_PATH" log --oneline HEAD --not --remotes 2>/dev/null) || UNPUSHED_RC=$?
        if [[ "$UNPUSHED_RC" -ne 0 ]]; then
            # Undecidable, and said so rather than implied clean (#569): an unborn
            # HEAD or an unreadable repo lands here, and in both there is nothing to
            # lose, so this falls open exactly as OCCUPANCY: unknown above does.
            # The sweep makes the opposite choice because a sweep that skips costs
            # nothing, while a helper that refuses blocks a merge that must complete
            # - the same asymmetry #887 recorded.
            echo "WORKTREE_REMOVE_UNPUSHED: unknown" >&2
            echo -e "${YELLOW}Note: could not determine whether this worktree holds unpushed commits.${NC}" >&2
        elif [[ -n "$UNPUSHED" ]] && landed_record_matches; then
            # The commits are on no remote REF, and they do not need to be: the
            # merge helper recorded this exact commit as landed before it deleted
            # the ref (issue #916). A squash rewrites the branch onto main under a
            # different sha, so `--not --remotes` is answering "reachable from a
            # remote ref", while the reader wants "did this land" - the same place
            # #566 records those two parting company.
            echo "WORKTREE_REMOVE_UNPUSHED: landed" >&2
        elif [[ -n "$UNPUSHED" ]]; then
            echo "WORKTREE_REMOVE_UNPUSHED: refused" >&2
            echo -e "${RED}Error: refusing to remove a worktree holding commits that are on no remote${NC}" >&2
            echo "" >&2
            printf '    %s
    ' "$UNPUSHED" >&2
            echo "" >&2
            echo "  These commits exist nowhere else (issue #899). With --delete-branch the" >&2
            echo "  branch ref goes too, leaving them reachable only by 'git fsck --lost-found'" >&2
            echo "  until gc runs. Push the branch, or pass --allow-unpushed if you are" >&2
            echo "  certain the commits are unwanted." >&2
            # NAME THE COUPLING (issue #1262). After a SQUASH merge these commits
            # are on no remote ref by construction, and the only evidence this
            # helper accepts that they LANDED is a record written by exactly one
            # caller. A PR merged any other way never gets it, and used to arrive
            # here described as unpushed work with no hint of why.
            echo "" >&2
            echo "  If this branch's PR has already MERGED: the only evidence this helper accepts" >&2
            echo "  that squashed commits landed is 'branch.${BRANCH_NAME}.cpp-merged-head', and" >&2
            echo "  its only writer is gh-pr-merge.sh. A PR merged any other way (the web UI, a" >&2
            echo "  plain 'gh pr merge') has no record and reads as unpushed here. Check the PR" >&2
            echo "  state, and if it merged at this exact HEAD, --allow-unpushed is safe." >&2
            exit 7
        else
            echo "WORKTREE_REMOVE_UNPUSHED: pushed" >&2
        fi
    fi
else
    # Silence is not a verdict (issue #916). `--allow-unpushed` emitted NO
    # marker at all, so a consumer parsing this output could not tell an
    # overridden check from a helper too old to have one - which is exactly the
    # version every container on this host is currently running.
    echo "WORKTREE_REMOVE_UNPUSHED: overridden" >&2
fi

# Remove the worktree
# --- Attribution refusal (issue #1032) - deliberately the LAST check ---------
# Every refusal above means "do not remove this worktree at all". This one means
# only "do not also delete the branch": its remedy is to re-run without
# --delete-branch, which still removes the directory. Running it earlier would
# hand that remedy to a caller whose tree is live-claimed or occupied, telling
# them to proceed with a removal the stronger guards had already refused. The
# weakest refusal must therefore be the last one reached, so it can only ever
# speak about a tree everything else has already cleared.
if [[ "$ATTRIBUTION_MISMATCH" == true && "$DELETE_BRANCH" == true && "$STEAL" != true ]]; then
    echo -e "${RED}Error: refusing --delete-branch on a worktree whose name disagrees with its branch${NC}" >&2
    echo "" >&2
    echo "  Directory: ${DIR_BASENAME}  -> says issue #${DIRNAME_ISSUE}" >&2
    echo "  Branch:    ${BRANCH_NAME}  -> IS issue #${BRANCH_ISSUE}" >&2
    echo "" >&2
    echo "  Removing the DIRECTORY is local and recoverable. Deleting the BRANCH is" >&2
    echo "  neither, and the branch that would be deleted - '${BRANCH_NAME}' - is not" >&2
    echo "  the one the path you named refers to. A caller who asked for issue" >&2
    echo "  #${DIRNAME_ISSUE} by path would silently lose issue #${BRANCH_ISSUE}'s branch." >&2
    echo "" >&2
    echo "  Re-run WITHOUT --delete-branch to remove just the directory, or rename the" >&2
    echo "  worktree to match its branch first. --force does not override this;" >&2
    echo "  --steal does, if you have confirmed which issue you mean." >&2
    exit 8
fi

# Every path cannot be deleted without write+execute on its PARENT directory -
# that permission governs unlink/rmdir, not the entry's own mode. `git worktree
# remove` can report SUCCESS (exit 0) while such a path survives it (observed
# with a read-only parent dir), and once it does, git has already forgotten the
# worktree, leaving a directory with no `.git` file that this script would then
# refuse on a retry as "not a git worktree" (Nit Store #864, comment
# 5983011277). This pre-scan refuses BEFORE deleting anything instead.
#
# READ is checked too, not just write+execute (Codex review, #864): a
# directory with write+execute but no read (mode 0300) passes a write/execute-
# only test, but `find` cannot enumerate what is inside it either - so the
# scan silently stopped at exactly the directory that should have been
# reported, and an incomplete walk read as "nothing wrong". Flagging that
# directory itself catches it without needing to see past it. `find`'s own
# exit status is also captured (into a file first, per this repo's own
# counter-model-reviewed idiom in check-ignored-additions.sh - a process
# substitution discards it) so a `find` that fails outright is read as
# "could not verify", never as a clean scan.
#
# The PARENT of the worktree ROOT is checked too: `find` only walks AT OR
# BELOW root, so emptying every descendant still leaves one more removal -
# `rmdir` on the root itself - which needs write+execute on a directory
# outside anything `find` ever saw.
#
# undeletable_find (and its sticky-bit-aware sticky_dir_is_safe helper,
# issue #1520) are defined earlier now (issue #1524), so
# --finish-partial-removal's own branch can call them too.

PRE_SCAN_RC=0
PRE_UNDELETABLE="$(undeletable_find "$WORKTREE_PATH")" || PRE_SCAN_RC=$?
if [[ "$PRE_SCAN_RC" -ne 0 ]]; then
    echo "WORKTREE_REMOVE_PRESCAN: unknown" >&2
    echo -e "${RED}Error: the permission scan itself failed - this is not the same as clean${NC}" >&2
    echo "  Re-run once the directory tree can be read." >&2
    exit 9
fi
if [[ -n "$PRE_UNDELETABLE" ]]; then
    echo "WORKTREE_REMOVE_PRESCAN: undeletable" >&2
    echo -e "${RED}Error: refusing to remove - some paths cannot be deleted${NC}" >&2
    echo "" >&2
    echo "  The following director{y,ies} lack read, write or execute permission, so" >&2
    echo "  git cannot remove entries inside them. Removing anyway risks a half-deleted" >&2
    echo "  worktree with no .git file (git can report success regardless):" >&2
    printf '    %s\n' "$PRE_UNDELETABLE" >&2
    echo "" >&2
    echo "  Fix permissions (e.g. chmod -R u+w) and re-run." >&2
    exit 9
fi
echo "WORKTREE_REMOVE_PRESCAN: clear" >&2

echo -e "${BLUE}Removing worktree: ${WORKTREE_PATH}${NC}"
if [[ "${CLAIM_STATE:-unknown}" == foreign ]]; then
    git -C "$WORKTREE_PATH" worktree unlock "$WORKTREE_PATH" >/dev/null 2>&1 || true
fi
git -C "$MAIN_REPO" worktree remove "$WORKTREE_PATH" $FORCE

echo -e "${GREEN}Worktree removed successfully.${NC}"

# Optionally delete the branch.
#
# --delete-branch is an explicit deletion request, and by this point the worktree
# has already been removed. Try the safe `git branch -d` first so a genuinely
# fully-merged branch is reported as such. When it refuses with "not fully
# merged", that is the EXPECTED squash-merge case: a squash rewrites the branch's
# commits into one new commit on main, so the branch tip is no longer an ancestor
# of main even though the PR is MERGED and the work is safely on main. Fall back
# to `git branch -D` non-interactively rather than prompting.
#
# The old interactive `read -p` confirmation broke every non-interactive caller
# (/flow:auto, /flow:merge): with stdin not a TTY, `read` hit EOF and returned
# non-zero, tripping `set -e` so the whole script exited non-zero AND left the
# branch undeleted - a false "cleanup failed" even though the worktree removal
# succeeded (issue #566). Branch-delete outcome never fails the script now: the
# worktree removal (above) is the only step whose failure surfaces non-zero.
if [[ "$DELETE_BRANCH" == true && -n "$BRANCH_NAME" && "$BRANCH_NAME" != "main" && "$BRANCH_NAME" != "master" ]]; then
    echo -e "${BLUE}Deleting branch: ${BRANCH_NAME}${NC}"

    if git -C "$MAIN_REPO" branch -d "$BRANCH_NAME" 2>/dev/null; then
        echo -e "${GREEN}Branch deleted (was fully merged).${NC}"
    elif git -C "$MAIN_REPO" branch -D "$BRANCH_NAME" 2>/dev/null; then
        # Expected for squash-merged PRs: the branch is not an ancestor of main,
        # so -d refuses; --delete-branch already authorized the deletion.
        echo -e "${GREEN}Branch force-deleted (squash-merged; not an ancestor of main).${NC}"
    else
        # Branch removal genuinely failed (e.g. already gone) - warn, do NOT fail
        # the run: the worktree was removed, which is this script's job.
        echo -e "${YELLOW}Could not delete branch '${BRANCH_NAME}' (may already be gone). Worktree removal still succeeded.${NC}"
    fi
fi

echo ""
echo -e "${GREEN}Done.${NC}"
