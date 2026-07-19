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
# Usage:
#   worktree-remove.sh <worktree-path> [--force] [--delete-branch] [--steal]
#
# Options:
#   --force          Remove even if worktree has uncommitted changes
#   --delete-branch  Also delete the associated branch after removal
#   --steal          Remove even when another live session claims it (#597)
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
        -h|--help)
            echo "Usage: worktree-remove.sh <worktree-path> [--force] [--delete-branch]"
            echo ""
            echo "Safely remove git worktrees. If you're currently inside the worktree"
            echo "being removed, the script automatically changes to the main repository"
            echo "first to prevent breaking your shell session."
            echo ""
            echo "Options:"
            echo "  --force          Remove even if worktree has uncommitted changes"
            echo "  --delete-branch  Also delete the associated branch after removal"
            echo "                   (force-deletes a squash-merged branch non-interactively)"
            echo "  --steal          Remove even when another live /flow session claims it"
            echo "                   (issue #597; without it a live claim is a hard stop)"
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
        self | stale)
            # Ours, or abandoned - drop the lock so the removal below can proceed.
            bash "$CLAIM_HELPER" release "$WORKTREE_PATH" >/dev/null 2>&1 || true
            ;;
    esac
fi

# Check for uncommitted changes (unless --force)
if [[ -z "$FORCE" ]]; then
    CHANGES=$(git -C "$WORKTREE_PATH" status --porcelain 2>/dev/null || echo "")
    if [[ -n "$CHANGES" ]]; then
        echo -e "${RED}Error: Worktree has uncommitted changes${NC}" >&2
        echo "" >&2
        git -C "$WORKTREE_PATH" status --short >&2
        echo "" >&2
        echo "Use --force to remove anyway, or commit/stash changes first." >&2
        exit 1
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
