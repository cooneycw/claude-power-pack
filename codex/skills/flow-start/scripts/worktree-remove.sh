#!/bin/bash
# worktree-remove.sh - Safely remove git worktrees
#
# If you're inside the worktree being removed, the script automatically
# changes to the main repository first (determined from the worktree's
# .git file) to prevent breaking your shell session.
#
# Usage:
#   worktree-remove.sh <worktree-path> [--force] [--delete-branch]
#
# Options:
#   --force          Remove even if worktree has uncommitted changes
#   --delete-branch  Also delete the associated branch after removal
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
