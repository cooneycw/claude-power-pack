#!/usr/bin/env bash
# CONSTRUCTED anchor for controls/flow-worktree-guard-leak (issue #1726).
#
# The plausible weaker guard: it establishes that this is a linked worktree -
# so there IS a separate main tree an edit could have leaked into - and stops
# there, reporting a clean look. "The run is in a worktree" mistaken for "the
# run's edits stayed in the worktree". It never reads the main tree's status,
# which is the whole of what the real guard does after this point.
set -uo pipefail
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "FLOW_WORKTREE_GUARD: not-applicable - not a git work tree"; exit 5
fi
git_dir="$(git rev-parse --git-dir 2>/dev/null)"
common="$(git rev-parse --git-common-dir 2>/dev/null)"
if [ -z "$git_dir" ] || [ -z "$common" ]; then
  echo "FLOW_WORKTREE_GUARD: unknown - git could not resolve this checkout's git dir or common dir"; exit 4
fi
if [ "$(cd "$git_dir" && pwd -P)" = "$(cd "$common" && pwd -P)" ]; then
  echo "FLOW_WORKTREE_GUARD: not-applicable - this is the main checkout"; exit 5
fi
echo "FLOW_WORKTREE_GUARD: no-leak - a linked worktree; edits made here stay here"
exit 0
