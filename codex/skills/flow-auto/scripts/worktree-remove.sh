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
#
# Options:
#   --force          Pass --force to git worktree remove; does not override
#                    any data-loss refusal
#   --delete-branch  Also delete the associated branch after removal
#   --steal          Remove even when another live session claims it (#597),
#                    or when it is in use by a live process (#888, #1032)
#   --allow-dirty    Remove even though uncommitted work would be destroyed
#   --allow-unpushed Remove even though commits exist on no remote ref
#
# Exit codes:
#   0  removed (or already absent - stale refs pruned)
#   1  usage, path, or repository validation error
#   4  claimed by another live /flow session (#597)
#   5  in use by a live process (#888, #1032)
#   6  holds uncommitted work without --allow-dirty (#899)
#   7  holds commits on no remote ref without --allow-unpushed (#899)
#   8  --delete-branch asked for, but the directory name and the checked-out
#      branch name different issues (#1032)
#
# Examples:
#   worktree-remove.sh /home/user/Projects/nhl-api-issue-42
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
            echo "                   (issue #899; exit 6 without it)"
            echo "  --allow-unpushed Remove even though commits exist on no remote ref"
            echo "                   (issue #899; exit 7 without it)"
            echo ""
            echo "Each refusal has its own override on purpose: one flag that silenced all"
            echo "three would be one flag away from silencing everything."
            echo ""
            echo "Exit codes:"
            echo "  0  removed (or already absent - stale refs pruned)"
            echo "  1  usage, path, or repository validation error"
            echo "  4  claimed by another live /flow session (#597)"
            echo "  5  in use by a live process (#888, #1032)"
            echo "  6  holds uncommitted work without --allow-dirty (#899)"
            echo "  7  holds commits on no remote ref without --allow-unpushed (#899)"
            echo "  8  --delete-branch asked for, but the directory name and the"
            echo "     checked-out branch name different issues (#1032)"
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
    echo "Usage: worktree-remove.sh <worktree-path> [--force] [--delete-branch] [--steal] [--allow-dirty] [--allow-unpushed]"
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
