# Flow: Merge PR and Clean Up

Merge the current branch's PR, then clean up the worktree and branch.

## Instructions

When the user invokes `/flow:merge`, perform these steps:

### Step 1: Detect Context

```bash
BRANCH=$(git branch --show-current)
REPO=$(basename "$(git rev-parse --show-toplevel)")

# Extract issue number
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")

# Detect if we're in a worktree
WORKTREE_PATH=$(pwd)
IS_WORKTREE=false
if [[ -f ".git" ]]; then
    IS_WORKTREE=true
fi
```

### Step 2: Find and Verify PR

```bash
PR_JSON=$(gh pr list --head "$BRANCH" --json number,state,mergeable,reviewDecision,statusCheckRollup --jq '.[0]')
```

- If no PR found: "No PR found for branch `$BRANCH`. Run `/flow:finish` first."
- If PR is already merged: "PR is already merged. Run cleanup only? [y/N]"
- Report PR state: checks passing, review status, mergeable

### Step 3: Merge the PR

```bash
PR_NUMBER=$(echo "$PR_JSON" | jq -r '.number')

# Squash merge (default) — keeps history clean
gh pr merge "$PR_NUMBER" --squash --delete-branch
```

- Use `--squash` by default (clean history)
- `--delete-branch` removes the remote branch automatically
- If merge fails (conflicts, checks failing), report and stop

### Step 4: Update Local Main

Determine the main repo path:

```bash
if [[ "$IS_WORKTREE" == true ]]; then
    # Get main repo path from worktree .git file
    MAIN_REPO=$(cat .git | sed 's/gitdir: //' | sed 's|/.git/worktrees/.*||')
else
    MAIN_REPO=$(pwd)
fi

# Pull latest main
git -C "$MAIN_REPO" checkout main
git -C "$MAIN_REPO" pull origin main
```

### Step 5: Clean Up Worktree

If we're in a worktree:

```bash
# Use the safe worktree removal script
if command -v worktree-remove.sh &>/dev/null || [[ -f ~/.claude/scripts/worktree-remove.sh ]]; then
    ~/.claude/scripts/worktree-remove.sh "$WORKTREE_PATH" --force --delete-branch
else
    # Manual cleanup (less safe but functional)
    cd "$MAIN_REPO"
    git worktree remove "$WORKTREE_PATH" --force
    git branch -D "$BRANCH" 2>/dev/null || true
fi
```

If we're in the main repo:
```bash
# Just delete the local branch
git branch -D "$BRANCH" 2>/dev/null || true
```

### Step 6: Close Issue (if linked)

```bash
if [[ -n "$ISSUE_NUM" ]]; then
    # Check if issue is still open (gh pr merge with Closes # may have closed it)
    ISSUE_STATE=$(gh issue view "$ISSUE_NUM" --json state --jq '.state' 2>/dev/null)
    if [[ "$ISSUE_STATE" == "OPEN" ]]; then
        gh issue close "$ISSUE_NUM" --comment "Closed via /flow:merge — PR #${PR_NUMBER} merged."
    fi
fi
```

### Step 7: Prune Stale Branches

After merge cleanup, prune any other stale references:

```bash
# Prune stale worktree references (folders deleted but git still tracking)
git -C "$MAIN_REPO" worktree prune

# Delete local issue-* branches that are fully merged to main
MERGED=$(git -C "$MAIN_REPO" branch --merged main | grep -v '^\*' | grep -v 'main$' | grep -v 'master$' | sed 's/^[ ]*//')
# Protect branches with active worktrees
WORKTREE_BRANCHES=$(git -C "$MAIN_REPO" worktree list --porcelain | grep "^branch " | sed 's|branch refs/heads/||')
for b in $MERGED; do
    echo "$WORKTREE_BRANCHES" | grep -q "^${b}$" && continue
    git -C "$MAIN_REPO" branch -d "$b" 2>/dev/null && echo "Deleted merged branch: $b"
done

# Prune stale remote tracking branches
git -C "$MAIN_REPO" fetch --prune
```

### Step 8: Output

```
PR #78 merged (squash) ✅

Cleanup:
  ✅ Remote branch deleted: issue-42-fix-login
  ✅ Worktree removed: ../my-project-issue-42
  ✅ Local branch deleted: issue-42-fix-login
  ✅ Issue #42 closed
  ✅ Pruned stale worktree references
  ✅ Deleted 2 merged local branches
  ✅ Pruned stale remote tracking branches

Current directory: /home/user/Projects/my-project (main)
```

## Error Handling

- **PR not found:** Direct user to `/flow:finish`
- **Merge conflicts:** Report conflict, suggest manual resolution
- **Checks failing:** Report which checks failed, ask if user wants to wait or force
- **Inside worktree being removed:** `worktree-remove.sh` handles this safely
- **Issue already closed:** Skip close step silently

## Notes

- Squash merge is the default — produces clean single-commit history
- The remote branch is deleted by `gh pr merge --delete-branch`
- The worktree removal uses the safe `worktree-remove.sh` script when available
- After merge, the user ends up in the main repo on the `main` branch
- Automatically prunes stale worktree references, merged branches, and remote tracking branches
- For a standalone cleanup (without merging), use `/flow:cleanup`
