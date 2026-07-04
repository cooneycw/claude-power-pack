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
# Transient un-mergeability (issue #485):
#   Right after a `git push`, GitHub is still asynchronously computing the PR's
#   mergeability, so `gh pr view --json mergeable` returns UNKNOWN for a beat and a
#   raw `gh pr merge` fails with "Pull Request is not mergeable". That is a purely
#   transient blip - a re-check moments later returns MERGEABLE and the squash
#   succeeds. To stop that from being a false STOP, poll mergeability before the
#   merge: proceed only on MERGEABLE, hard-stop on a genuine CONFLICTING, and
#   fail-open (attempt the merge anyway) if it never resolves - the post-merge
#   MERGED-state check below stays the final backstop.
#
# Base moved at squash time (issue #502):
#   The pre-merge poll structurally cannot catch a sibling PR that merges in the
#   poll->merge race window: the squash then fails with "Base branch was
#   modified. Review and try the merge again." even though a refetch + re-attempt
#   succeeds moments later (observed live on the flow:auto #485 run itself). On
#   that specific error - and no other - refetch, re-poll mergeability, and
#   re-attempt the squash a bounded number of times before reporting failure.
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
#   GH_PR_MERGE_GH             override the `gh` binary (default: gh)
#   GH_PR_MERGE_GIT            override the `git` binary (default: git)
#   GH_PR_MERGE_POLL_ATTEMPTS  mergeability poll attempts (default: 5)
#   GH_PR_MERGE_POLL_DELAY     seconds between poll attempts (default: 2)
#   GH_PR_MERGE_BASE_RETRY_ATTEMPTS  squash retries on "Base branch was modified" (default: 2)
#   GH_PR_MERGE_BASE_RETRY_DELAY     seconds before each such retry (default: 2)

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

# Wait out a transient `mergeable=UNKNOWN` before attempting the squash (issue
# #485). Returns 0 to proceed (MERGEABLE, or fail-open after the poll never
# resolved), 1 to stop (genuine CONFLICTING).
poll_mergeable() {
    local attempts="${GH_PR_MERGE_POLL_ATTEMPTS:-5}"
    local delay="${GH_PR_MERGE_POLL_DELAY:-2}"
    local i mergeable
    for ((i = 1; i <= attempts; i++)); do
        mergeable=$("$GH_BIN" pr view "$PR_NUMBER" --json mergeable --jq '.mergeable' 2>/dev/null)
        case "$mergeable" in
            MERGEABLE)
                return 0
                ;;
            CONFLICTING)
                echo "error: PR #$PR_NUMBER is not mergeable (mergeable: CONFLICTING) -" \
                     "resolve the conflicts, then re-run." >&2
                return 1
                ;;
            *)
                # UNKNOWN or empty: GitHub is still computing mergeability. Wait and
                # retry, unless this was the last attempt (then fall through to
                # fail-open below).
                if [[ $i -lt $attempts ]]; then
                    sleep "$delay"
                fi
                ;;
        esac
    done
    # Never resolved - fail open: attempt the merge and let the post-merge
    # MERGED-state verification be the arbiter, rather than STOP on a transient.
    echo "note: mergeability still UNKNOWN for PR #$PR_NUMBER after $attempts" \
         "check(s); attempting the merge anyway (post-merge state check is the" \
         "backstop)." >&2
    return 0
}

if ! poll_mergeable; then
    exit 1
fi

# Attempt the squash, retrying (bounded) only when the base moved under us at
# squash time (issue #502). Sets the global merge_exit; any error other than
# "Base branch was modified" is NOT retried, and the post-merge MERGED-state
# verification below remains the final arbiter either way.
run_squash() {
    # $@: extra gh flags (--delete-branch in the primary repo)
    local retries="${GH_PR_MERGE_BASE_RETRY_ATTEMPTS:-2}"
    local delay="${GH_PR_MERGE_BASE_RETRY_DELAY:-2}"
    local errfile attempt
    errfile=$(mktemp)
    for ((attempt = 0; attempt <= retries; attempt++)); do
        if (( attempt > 0 )); then
            echo "note: base branch moved under PR #$PR_NUMBER at squash time" \
                 "(sibling merge race, issue #502) - refetching and retrying" \
                 "(${attempt}/${retries})." >&2
            "$GIT_BIN" fetch origin >/dev/null 2>&1 || true
            sleep "$delay"
            # The sibling merge may have made the PR genuinely CONFLICTING -
            # re-poll so that stops us with the clear conflict message instead
            # of a retry that can never succeed.
            if ! poll_mergeable; then
                merge_exit=1
                break
            fi
        fi
        "$GH_BIN" pr merge "$PR_NUMBER" --squash "$@" 2>"$errfile"
        merge_exit=$?
        cat "$errfile" >&2
        if [[ $merge_exit -eq 0 ]] || ! grep -q "Base branch was modified" "$errfile"; then
            break
        fi
    done
    rm -f "$errfile"
}

if in_linked_worktree; then
    run_squash
    # Delete the remote branch ourselves - this is what --delete-branch would have
    # done, minus the local branch switch that fails in a linked worktree.
    if [[ $merge_exit -eq 0 ]]; then
        "$GIT_BIN" push origin --delete "$BRANCH" >/dev/null 2>&1 || true
    fi
else
    run_squash --delete-branch
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
