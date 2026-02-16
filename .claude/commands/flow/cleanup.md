---
description: Clean up stale worktree references and merged branches
allowed-tools: Bash(git:*), Bash(grep:*), Bash(wc:*), Bash(echo:*), Read
---

# Flow: Cleanup — Prune Stale Worktrees and Branches

Remove orphaned worktree references, delete local branches already merged to main, and prune stale remote tracking branches.

## Arguments

- No arguments required. Run from the main repo or any worktree.

## Instructions

When the user invokes `/flow:cleanup`, perform these steps:

### Step 1: Detect Repository Root

```bash
# Find the main repo (works from worktree or main)
if [[ -f ".git" ]]; then
    MAIN_REPO=$(cat .git | sed 's/gitdir: //' | sed 's|/.git/worktrees/.*||')
else
    MAIN_REPO=$(git rev-parse --show-toplevel)
fi
REPO=$(basename "$MAIN_REPO")
```

### Step 2: Prune Stale Worktree References

When worktree folders are deleted manually, git still tracks them. This cleans those references.

```bash
# Show stale worktree references before pruning
STALE_WORKTREES=$(git -C "$MAIN_REPO" worktree list --porcelain | grep -B2 "prunable" | grep "worktree " | sed 's/worktree //' || true)

# Prune them
git -C "$MAIN_REPO" worktree prune
```

Report what was pruned (or "No stale worktree references found").

### Step 3: Find and Delete Merged Local Branches

Delete local `issue-*` branches that have been merged to main. Protect `main`, `master`, and any branch with an active worktree.

```bash
# Get list of branches with active worktrees (these are protected)
WORKTREE_BRANCHES=$(git -C "$MAIN_REPO" worktree list --porcelain | grep "^branch " | sed 's|branch refs/heads/||')

# Make sure main is up to date
git -C "$MAIN_REPO" fetch origin main

# Find merged branches (excluding main/master and worktree branches)
MERGED_BRANCHES=$(git -C "$MAIN_REPO" branch --merged main | grep -v '^\*' | grep -v 'main$' | grep -v 'master$' | sed 's/^[ ]*//')
```

For each merged branch:
1. Skip if it has an active worktree
2. Delete it with `git -C "$MAIN_REPO" branch -d "$BRANCH"`

**Important:** Some branches from squash-merged PRs won't show as `--merged`. Also check for branches whose remote counterpart has been deleted:

```bash
# Find local issue-* branches whose remote tracking branch is gone
for branch in $(git -C "$MAIN_REPO" branch | grep 'issue-' | sed 's/^[ *]*//' ); do
    # Skip if branch has an active worktree
    echo "$WORKTREE_BRANCHES" | grep -q "^${branch}$" && continue

    # Check if remote tracking branch exists
    REMOTE=$(git -C "$MAIN_REPO" config "branch.${branch}.remote" 2>/dev/null || echo "")
    MERGE_REF=$(git -C "$MAIN_REPO" config "branch.${branch}.merge" 2>/dev/null || echo "")

    if [[ -n "$REMOTE" && -n "$MERGE_REF" ]]; then
        REMOTE_REF="refs/remotes/${REMOTE}/$(echo "$MERGE_REF" | sed 's|refs/heads/||')"
        if ! git -C "$MAIN_REPO" show-ref --verify --quiet "$REMOTE_REF" 2>/dev/null; then
            # Remote branch is gone — safe to delete locally
            # (The PR was merged and remote branch deleted)
            echo "Remote deleted: $branch"
        fi
    fi
done
```

For branches where the remote was deleted (PR merged + `--delete-branch`), use `git branch -D` since squash merges don't register as fully merged.

Report each branch deleted and the reason (merged to main, or remote branch deleted).

### Step 4: Prune Stale Remote Tracking Branches

```bash
git -C "$MAIN_REPO" fetch --prune
```

This removes `remotes/origin/issue-*` references for branches already deleted on the remote.

Report how many remote tracking branches were pruned.

### Step 5: Summary Output

```markdown
## Flow Cleanup — {repo}

### Worktree References
  {N} stale references pruned (or "None found")

### Local Branches Deleted
  {branch-1} (merged to main)
  {branch-2} (remote branch deleted — squash-merged PR)
  ... or "No stale branches found"

### Remote Tracking Branches
  {N} stale remote references pruned (or "Already clean")

### Current State
  {M} worktrees active
  {N} local issue branches remaining
```

## Error Handling

- **Not a git repo:** Report error and exit
- **Uncommitted changes on a branch:** Never delete — skip and warn
- **Protected branches:** Never delete `main` or `master`
- **Active worktree branches:** Never delete branches with active worktrees

## Notes

- Safe to run multiple times (fully idempotent)
- Only deletes `issue-*` pattern branches in the squash-merge detection path (other branches require `--merged` confirmation)
- Use `git branch -d` (safe delete) for merged branches, `git branch -D` (force) only for branches whose remote was deleted
- Run automatically after `/flow:merge` or manually anytime
- Does not require network access except for `git fetch --prune`
