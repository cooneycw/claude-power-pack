## Findings

- **MEDIUM - scripts/stash-worktree-guard.sh:88**: `git stash drop` races a concurrent push; the index it drops can belong to another session by the time it runs.
- **MEDIUM - scripts/stash-worktree-guard.sh:41**: `core.hooksPath` is ignored, so the guard installs into a hooks directory git never reads.
- **LOW - scripts/stash-worktree-guard.sh:120**: `--check` accepts a hook file that is not executable.
- **LOW - scripts/stash-worktree-guard.sh:64**: the tag match is a substring match, so one tag can claim another's entry.

## Red cases

- a hook directory set via `core.hooksPath`
