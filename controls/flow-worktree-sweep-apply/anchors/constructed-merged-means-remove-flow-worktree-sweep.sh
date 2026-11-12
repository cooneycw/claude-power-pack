#!/usr/bin/env bash
# CONSTRUCTED anchor for controls/flow-worktree-sweep-apply (issue #1726).
#
# The naive sweep: "the pull request merged, so the worktree is finished".
# It asks GitHub whether the branch has a merged PR and, if so, removes the
# worktree. It never compares the merged head with the local tip, so a commit
# made after the merge and never pushed is deleted with the checkout. And when
# GitHub cannot answer it keeps the worktree and reports the run clean, where
# the real sweep says it could not tell and marks the run partial.
#
# DESTRUCTIVE BY CONSTRUCTION. It is only ever invoked by this control's
# run-case.sh, which builds its target under one temporary directory and
# refuses to invoke anything if a worktree of that repository lies outside it.
set -uo pipefail
repo="" apply=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) repo="${2:-}"; shift ;;
    --apply) apply=true ;;
  esac
  shift
done
[ -n "$repo" ] || { echo "FLOW_WORKTREE_SWEEP: error" >&2; exit 1; }
main="$(git -C "$repo" rev-parse --show-toplevel)"
cur=""
git -C "$repo" worktree list --porcelain | while IFS= read -r line; do
  case "$line" in
    "worktree "*) cur="${line#worktree }" ;;
    "branch refs/heads/"*)
      branch="${line#branch refs/heads/}"
      [ "$cur" = "$main" ] && continue
      state="$(gh pr list --head "$branch" 2>/dev/null | head -1 | cut -d'|' -f1)"
      if [ "$state" = MERGED ]; then
        if [ "$apply" = true ]; then
          git -C "$repo" worktree remove --force "$cur" >/dev/null 2>&1
          echo "SWEEP_WORKTREE: $cur removed MERGED,branch=$branch"
        else
          echo "SWEEP_WORKTREE: $cur removable MERGED,branch=$branch"
        fi
      else
        echo "SWEEP_WORKTREE: $cur skip pr-none"
      fi ;;
  esac
done
echo "FLOW_WORKTREE_SWEEP: ok"
exit 0
