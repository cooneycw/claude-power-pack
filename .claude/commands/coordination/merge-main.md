# Coordinated Merge to Main

> **Requires:** `extras/redis-coordination/scripts/` installed to `~/.claude/scripts/`. See `extras/redis-coordination/README.md`.

Merge a PR branch to main with session locking to prevent merge race conditions.

## When to Use

- After PR is approved and CI passes
- From the **main repository directory** (not a worktree)
- When you want to merge and clean up a completed PR

## Workflow

1. **Acquire Lock**
   - Lock name: `merge-{repo}-main`
   - Only one session can merge to main at a time

2. **Validate State**
   - Ensure we're in main repo (not worktree)
   - Ensure the PR branch exists

3. **Merge**
   - Checkout main
   - Pull latest
   - Merge the PR branch
   - Push to origin

4. **Cleanup (optional)**
   - Delete local branch
   - Delete remote branch
   - Remove worktree if exists

5. **Release Lock**

## Instructions

When the user invokes `/coordination:merge-main [BRANCH]`, perform these steps:

### Step 1: Validate Environment
```bash
# Ensure we're in main repo directory
if [[ "$(basename $(pwd))" =~ issue- ]]; then
    echo "ERROR: Must run from main repo directory, not a worktree"
    echo "Current directory: $(pwd)"
    exit 1
fi

# Ensure we're on main branch or can switch to it
git fetch origin
git checkout main
git pull origin main
```

### Step 2: Acquire Lock
```bash
REPO=$(basename $(git rev-parse --show-toplevel))
LOCK_NAME="merge-${REPO}-main"

~/.claude/scripts/session-lock.sh acquire "$LOCK_NAME" 180
```

If lock acquisition fails, inform the user which session holds the lock.

### Step 3: Verify PR Status (optional)
```bash
# Check PR is merged/ready
PR_STATE=$(gh pr view "$BRANCH" --json state --jq '.state')
if [[ "$PR_STATE" != "OPEN" && "$PR_STATE" != "MERGED" ]]; then
    echo "WARNING: PR state is $PR_STATE"
fi
```

### Step 4: Merge
```bash
BRANCH="$1"  # e.g., issue-170-progress-chart

# Option A: Fast-forward merge (if possible)
git merge "$BRANCH" --ff-only

# Option B: Squash merge (if user prefers)
git merge --squash "$BRANCH"
git commit -m "Merge $BRANCH"

# Push
git push origin main
```

### Step 5: Cleanup
```bash
# Delete local branch
git branch -d "$BRANCH"

# Delete remote branch
git push origin --delete "$BRANCH"

# Remove worktree if exists
WORKTREE_PATH="${REPO}-${BRANCH%%%-*}"  # e.g., nhl-api-issue-170
if git worktree list | grep -q "$WORKTREE_PATH"; then
    git worktree remove "$WORKTREE_PATH"
fi
```

### Step 6: Release Lock
```bash
~/.claude/scripts/session-lock.sh release "$LOCK_NAME"
```

## Example Usage

```
User: /coordination:merge-main issue-170-progress-chart

Claude: I'll merge issue-170-progress-chart to main with coordination.

[Acquiring lock: merge-nhl-api-main]
[Checking out main and pulling latest]
[Merging issue-170-progress-chart]
[Pushing to origin]
[Cleaning up branch and worktree]
[Releasing lock]

Successfully merged issue-170-progress-chart to main.
- Deleted local branch
- Deleted remote branch
- Removed worktree: /home/cooneycw/Projects/nhl-api-issue-170
```

## Safety Checks

Before merging, verify:
- [ ] All CI checks pass
- [ ] PR is approved (if required)
- [ ] No conflicts with main
- [ ] Tests pass locally

## Error Handling

- **Lock unavailable**: Report which session holds it
- **Merge conflicts**: Release lock and report conflict
- **Push fails**: Release lock and report error
- **Cleanup fails**: Warn but don't fail (lock still released)

Always release the lock in finally/cleanup block.

## Arguments

- `BRANCH` (required): The branch to merge (e.g., `issue-170-progress-chart`)
- `--squash`: Use squash merge instead of fast-forward
- `--no-cleanup`: Skip branch and worktree deletion
