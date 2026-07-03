#!/usr/bin/env bash
# gh-pr-merge.sh - Squash-merge a PR robustly from any git worktree layout.
#
# Problem (issue #461):
#   From inside a LINKED worktree - a native `.claude/worktrees/<name>` checkout
#   or a legacy sibling dir - `gh pr merge <N> --squash --delete-branch` fails
#   AFTER the remote merge has already succeeded:
#
#     failed to run git: fatal: 'main' is already checked out at '<main-repo>'
#
#   gh, having merged and deleted the remote branch, tries to switch THIS worktree
#   off the now-gone branch onto the default branch - which is checked out in the
#   primary worktree, so the local checkout errors and gh exits non-zero. The
#   remote squash still landed (and `Closes #N` still fired); only gh's local
#   post-merge step failed. Callers that trust the exit code read this as a failed
#   merge and stop - a false negative that cost a full re-diagnosis on flow:auto
#   #433.
#
# This wrapper makes the merge layout-aware:
#   * Linked worktree (cwd's `.git` is a FILE): run `gh pr merge --squash` WITHOUT
#     --delete-branch so gh never attempts the local branch switch, then delete the
#     REMOTE branch ourselves (what --delete-branch would have done). Local worktree
#     + branch removal is left to the caller (worktree-remove.sh / ExitWorktree),
#     so the native cleanup path is unaffected.
#   * Primary repo (cwd's `.git` is a DIRECTORY): keep --delete-branch; the local
#     switch to the default branch is safe there.
#   * Either way, verify the PR actually reached MERGED before returning non-zero,
#     so a stray local post-merge error is never mistaken for a merge failure.
#
# Usage:  gh-pr-merge.sh <pr-number> <branch-name>
# Exit:   0 if the PR is merged on the remote; 1 only if it genuinely did not merge.
#
# Env (test hooks - unset in normal use):
#   GH_PR_MERGE_GH   override the `gh` binary (default: gh)
#   GH_PR_MERGE_GIT  override the `git` binary (default: git)

set -uo pipefail

PR_NUMBER="${1:-}"
BRANCH="${2:-}"

if [[ -z "$PR_NUMBER" || -z "$BRANCH" ]]; then
    echo "Usage: gh-pr-merge.sh <pr-number> <branch-name>" >&2
    exit 2
fi

GH_BIN="${GH_PR_MERGE_GH:-gh}"
GIT_BIN="${GH_PR_MERGE_GIT:-git}"

# A linked worktree has a `.git` FILE (a gitdir pointer); the primary repo has a
# `.git` DIRECTORY. This is the exact condition under which --delete-branch trips.
in_linked_worktree() { [[ -f .git ]]; }

if in_linked_worktree; then
    "$GH_BIN" pr merge "$PR_NUMBER" --squash
    merge_exit=$?
    # Delete the remote branch ourselves - this is what --delete-branch would have
    # done, minus the local branch switch that fails in a linked worktree.
    if [[ $merge_exit -eq 0 ]]; then
        "$GIT_BIN" push origin --delete "$BRANCH" >/dev/null 2>&1 || true
    fi
else
    "$GH_BIN" pr merge "$PR_NUMBER" --squash --delete-branch
    merge_exit=$?
fi

# Trust the PR state over the exit code: a non-zero from a local post-merge step
# must never mask a remote merge that actually succeeded.
state=$("$GH_BIN" pr view "$PR_NUMBER" --json state --jq '.state' 2>/dev/null)

if [[ "$state" == "MERGED" ]]; then
    if [[ $merge_exit -ne 0 ]]; then
        echo "note: gh exited $merge_exit but PR #$PR_NUMBER is MERGED - a local" \
             "post-merge step failed, not the merge itself. Continuing." >&2
        # Ensure the remote branch is gone even if the failure preceded our push.
        if in_linked_worktree; then
            "$GIT_BIN" push origin --delete "$BRANCH" >/dev/null 2>&1 || true
        fi
    fi
    echo "merged"
    exit 0
fi

echo "error: PR #$PR_NUMBER did not merge (state: ${state:-unknown})." >&2
exit 1
