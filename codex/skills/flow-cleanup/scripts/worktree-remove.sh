#!/bin/bash
# worktree-remove.sh - Safely remove git worktrees
#
# If you're inside the worktree being removed, the script automatically
# changes to the main repository first (determined from the worktree's
# .git file) to prevent breaking your shell session.
#
# A worktree CLAIMED by another live /flow session (issue #597) is never
# removed: the claim is checked first and a live foreign owner is a hard stop
# (exit 4), because removing it is exactly the silent-data-loss failure that
# motivated the claim. A self-owned or stale claim is released and removed as
# usual, and --steal is the deliberate override.
#
# A claim only protects a worktree where one was staked, though, and `free`,
# `unsupported` and `unknown` are not claims. So a worktree that no claim names
# is checked a second way (issue #888): if a live process has its working
# directory inside it AND it holds uncommitted work, removal is refused (exit
# 5). --force does NOT suppress that refusal - --force is what every /flow:auto
# Step 7 passes, so a guard it silences never fires where the damage happens.
# --steal overrides it as usual. On a host with no readable /proc the check
# reports `unknown` and falls open, rather than reporting a clean result it did
# not establish.
#
# Usage:
#   worktree-remove.sh <worktree-path> [--force] [--delete-branch] [--steal]
#
# Options:
#   --force          Remove even if worktree has uncommitted changes
#                    (does not override the #888 in-use refusal)
#   --delete-branch  Also delete the associated branch after removal
#   --steal          Remove even when another live session claims it (#597),
#                    or when it is in use with uncommitted work (#888)
#
# Exit codes:
#   0  removed (or already absent - stale refs pruned)
#   1  usage error, not a worktree, or uncommitted changes without --force
#   4  claimed by another live /flow session (#597)
#   5  in use by a live process AND holding uncommitted work (#888)
#
# Examples:
#   worktree-remove.sh /home/user/Projects/nhl-api-issue-42
#   worktree-remove.sh ../nhl-api-issue-42 --delete-branch
#   worktree-remove.sh /home/user/Projects/nhl-api-issue-42 --force --delete-branch

set -euo pipefail

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
            echo "Usage: worktree-remove.sh <worktree-path> [--force] [--delete-branch]"
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
            echo "                   (issue #899; exit 6 without it)"
            echo "  --allow-unpushed Remove even though commits exist on no remote ref"
            echo "                   (issue #899; exit 7 without it)"
            echo ""
            echo "Each refusal has its own override on purpose: one flag that silenced all"
            echo "three would be one flag away from silencing everything."
            echo ""
            echo "Examples:"
            echo "  worktree-remove.sh /home/user/Projects/nhl-api-issue-42"
            echo "  worktree-remove.sh ../nhl-api-issue-42 --delete-branch"
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
    echo "Usage: worktree-remove.sh <worktree-path> [--force] [--delete-branch]"
    exit 1
fi

# Resolve to absolute path
if [[ "$WORKTREE_PATH" != /* ]]; then
    WORKTREE_PATH="$(cd "$(dirname "$WORKTREE_PATH")" 2>/dev/null && pwd)/$(basename "$WORKTREE_PATH")"
fi

# Normalize path (remove trailing slash)
WORKTREE_PATH="${WORKTREE_PATH%/}"

# Get current working directory
CWD="$(pwd 2>/dev/null || echo "")"
CWD="${CWD%/}"

# Check if we're inside the worktree being removed
INSIDE_WORKTREE=false
if [[ -n "$CWD" && "$CWD" == "$WORKTREE_PATH"* ]]; then
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
    echo -e "${RED}Error: ${WORKTREE_PATH} is not a git worktree${NC}" >&2
    echo "(Worktrees have a .git file, not a .git directory)" >&2
    exit 1
fi

# Get the main repository path from the worktree's .git file
MAIN_REPO=$(cat "$WORKTREE_PATH/.git" | sed 's/gitdir: //' | sed 's|/.git/worktrees/.*||')

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

# --- Cross-session claim check (issue #597) ----------------------------------
# Another LIVE /flow session may be driving this checkout right now. Removing it
# out from under that session is the silent-data-loss failure this guard exists
# for, so a live foreign claim is a hard stop. A claim owned by THIS session, or
# left behind by a session that has since died, is simply released first.
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

    case "${CLAIM_STATE:-unknown}" in
        held | foreign)
            if [[ "$STEAL" != true ]]; then
                echo -e "${RED}Error: refusing to remove a worktree claimed by another session${NC}" >&2
                echo "" >&2
                echo "  Worktree: $WORKTREE_PATH" >&2
                echo "  Claim:    ${CLAIM_STATE} (issue #${CLAIM_ISSUE:--}, pid ${CLAIM_PID:--}, session ${CLAIM_SESSION:--})" >&2
                echo "" >&2
                echo "  Another /flow session is driving this checkout. Removing it would destroy" >&2
                echo "  its uncommitted work - the failure this claim exists to prevent (issue #597)." >&2
                echo "  Wait for that session to finish, or pass --steal if you are certain it is gone." >&2
                exit 4
            fi
            echo -e "${YELLOW}Warning: --steal given; removing a worktree claimed by pid ${CLAIM_PID:--}.${NC}" >&2
            bash "$CLAIM_HELPER" release "$WORKTREE_PATH" --force >/dev/null 2>&1 || true
            ;;
        self)
            # Ours - drop the lock so the removal below can proceed.
            bash "$CLAIM_HELPER" release "$WORKTREE_PATH" >/dev/null 2>&1 || true
            CLAIM_OWNED_BY_US=true
            ;;
        stale)
            # The claiming session died. Drop its lock, but do NOT treat that as
            # proof the checkout is idle: a test run or server it started can
            # outlive it, reparented and still writing here (issue #888).
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
# The claim above protects a worktree only where one was actually staked. Three
# states leave it unprotected - `free` (no claim ever filed), `unsupported` (git
# too old to lock) and `unknown` (the lock could not be read) - and an unclaimed
# worktree is indistinguishable from an idle one, so it was removed.
#
# That is how a LIVE session loses unsaved work. On 2026-09-13 a session sitting
# in `flow-finish-gate` held a 21KB staged file in a worktree reporting
# CLAIM=free; the only thing between it and deletion was the #503 mtime
# heuristic, whose 30-minute window that session had already outlived by being
# in a long test run. Both guards read "clear" on a checkout that was plainly
# occupied.
#
# So when the claim did not positively name THIS session as owner, ask a second
# question no time window can blind: is a live process sitting in it? A worktree
# someone is standing in, holding work that exists nowhere else, is not ours to
# delete. Unlike the dirty-tree check below, --force does NOT suppress this one:
# --force is precisely what every /flow:auto Step 7 passes, so a guard it
# silences is a guard that never fires where the damage happens. --steal remains
# the deliberate override.

# /proc/<pid>/cwd is fully resolved, so compare against a resolved path.
WT_REAL="$(readlink -f "$WORKTREE_PATH" 2>/dev/null || echo "$WORKTREE_PATH")"

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
        # Occupied but clean: nothing unrecoverable to lose, so removal stands.
        echo "WORKTREE_REMOVE_OCCUPANCY: occupied-clean" >&2
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
fi
echo "WORKTREE_REMOVE_DIRTY: clean" >&2

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
            exit 7
        else
            echo "WORKTREE_REMOVE_UNPUSHED: pushed" >&2
        fi
    fi
fi

# Remove the worktree
echo -e "${BLUE}Removing worktree: ${WORKTREE_PATH}${NC}"
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
