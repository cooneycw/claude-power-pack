# Flow: Sync — Push WIP to Remote for Cross-Machine Pickup

Push the current branch to the remote so you can continue work on another machine. Optional feature — most users won't need this.

## Arguments

None. Operates on the current worktree/branch.

## Instructions

When the user invokes `/flow:sync`, perform these steps:

### Step 1: Validate Context

```bash
# Ensure we're in a git repo
git rev-parse --show-toplevel

# Get current branch
BRANCH=$(git branch --show-current)
```

- If on `main` or `master`: **STOP**. Report: "Cannot sync main branch. Use `/flow:start <issue>` to create a worktree first."
- If not on an `issue-*` branch: Warn but allow (user may have custom branch names).

### Step 2: Check for Uncommitted Changes

```bash
# Check working tree status
git status --short
```

- **If clean:** Skip to Step 3.
- **If dirty (uncommitted changes):** Auto-commit as WIP:
  ```bash
  git add -A
  git commit -m "wip: sync work in progress

  Auto-committed by /flow:sync for cross-machine pickup.
  This commit will be squash-merged — no need to clean up."
  ```
  Report: "Auto-committed WIP changes."

### Step 3: Push to Remote

```bash
git push -u origin "$BRANCH"
```

- If push fails (e.g., rejected): Report the error and suggest `git pull --rebase origin "$BRANCH"` to resolve.

### Step 4: Output

```
Synced branch to remote.

  Branch: issue-42-fix-login-bug
  Remote: origin

  To continue on another machine:
    /flow:start 42
    → Detects remote branch and creates worktree from it
```

## Error Handling

- **Not in a git repo:** Report error clearly.
- **On main branch:** Block sync, suggest `/flow:start`.
- **Push rejected:** Suggest `git pull --rebase` to reconcile.
- **No remote configured:** Report "No remote 'origin' found."

## Notes

- This command is intentionally simple — just commit WIP + push.
- `/flow:start` already handles the receiving end (detects remote branches and creates worktrees tracking them).
- WIP commits are harmless because `/flow:merge` uses squash-merge, collapsing all commits into one clean commit.
- No configuration required — works with any git remote.
