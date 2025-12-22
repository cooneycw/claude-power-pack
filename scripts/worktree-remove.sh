#!/bin/bash
# worktree-remove.sh - Safely remove git worktrees
#
# Prevents the classic mistake of removing a worktree while working from it,
# which breaks the shell session completely.
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
            echo "Safely remove git worktrees with protection against removing"
            echo "the current working directory (which breaks shell sessions)."
            echo ""
            echo "Options:"
            echo "  --force          Remove even if worktree has uncommitted changes"
            echo "  --delete-branch  Also delete the associated branch after removal"
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

# CRITICAL SAFETY CHECK: Don't remove the worktree we're currently in
if [[ -n "$CWD" && "$CWD" == "$WORKTREE_PATH"* ]]; then
    echo -e "${RED}ERROR: Cannot remove worktree - you are currently working in it!${NC}" >&2
    echo "" >&2
    echo -e "${YELLOW}Current directory: ${CWD}${NC}" >&2
    echo -e "${YELLOW}Worktree to remove: ${WORKTREE_PATH}${NC}" >&2
    echo "" >&2
    echo "Removing this worktree would break your shell session." >&2
    echo "" >&2
    echo -e "${BLUE}To safely remove this worktree:${NC}" >&2
    echo "  1. Change to the main repository: cd /path/to/main-repo" >&2
    echo "  2. Then run this command again" >&2
    echo "" >&2
    echo -e "${BLUE}Or start a new Claude Code session from the main repo.${NC}" >&2
    exit 1
fi

# Check if worktree exists
if [[ ! -d "$WORKTREE_PATH" ]]; then
    echo -e "${YELLOW}Warning: Worktree directory does not exist: ${WORKTREE_PATH}${NC}"
    echo "It may have already been removed. Running 'git worktree prune'..."

    # Find the main repo by looking for a non-worktree .git directory
    # Try common parent patterns
    for parent in "$(dirname "$WORKTREE_PATH")"/*; do
        if [[ -d "$parent/.git" && ! -f "$parent/.git" ]]; then
            git -C "$parent" worktree prune
            echo -e "${GREEN}Pruned stale worktree references.${NC}"
            break
        fi
    done
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

# Optionally delete the branch
if [[ "$DELETE_BRANCH" == true && -n "$BRANCH_NAME" && "$BRANCH_NAME" != "main" && "$BRANCH_NAME" != "master" ]]; then
    echo -e "${BLUE}Deleting branch: ${BRANCH_NAME}${NC}"

    # Check if branch was merged (use -d) or force delete (-D)
    if git -C "$MAIN_REPO" branch -d "$BRANCH_NAME" 2>/dev/null; then
        echo -e "${GREEN}Branch deleted (was fully merged).${NC}"
    else
        # Branch wasn't merged - for squash-merged PRs, this is expected
        echo -e "${YELLOW}Branch not fully merged (normal for squash-merged PRs).${NC}"
        read -p "Force delete branch '$BRANCH_NAME'? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git -C "$MAIN_REPO" branch -D "$BRANCH_NAME"
            echo -e "${GREEN}Branch force-deleted.${NC}"
        else
            echo "Branch kept."
        fi
    fi
fi

echo ""
echo -e "${GREEN}Done.${NC}"
