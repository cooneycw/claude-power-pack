# Flow: Status of Active Worktrees

Show all active worktrees with their issue, branch, dirty state, and PR status.

## Instructions

When the user invokes `/flow:status`, perform these steps:

### Step 1: Detect Repository

```bash
REPO=$(basename "$(git rev-parse --show-toplevel)")
```

### Step 2: List Worktrees

```bash
git worktree list
```

### Step 3: For Each Worktree, Gather State

For each worktree (skip the main repo entry):

```bash
# Get branch name
BRANCH=$(git -C "$WORKTREE_PATH" branch --show-current 2>/dev/null)

# Extract issue number from branch name (issue-N-*)
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")

# Check for uncommitted changes
DIRTY=$(git -C "$WORKTREE_PATH" status --porcelain 2>/dev/null | wc -l)

# Check for unpushed commits
UNPUSHED=$(git -C "$WORKTREE_PATH" rev-list --count origin/main..HEAD 2>/dev/null || echo "0")

# Check PR status (if branch is pushed)
if [[ -n "$BRANCH" ]]; then
    PR_INFO=$(gh pr list --head "$BRANCH" --json number,url,state --jq '.[0]' 2>/dev/null || echo "")
fi
```

### Step 4: Fetch Issue Titles

For each detected issue number:
```bash
ISSUE_TITLE=$(gh issue view "$ISSUE_NUM" --json title --jq '.title' 2>/dev/null || echo "Unknown")
```

### Step 5: Output

```markdown
## Flow Status — {repo}

| Worktree | Issue | Branch | Status | PR |
|----------|-------|--------|--------|----|
| ../{repo}-issue-42 | #42 Fix login bug | issue-42-fix-login | 3 dirty files, 2 unpushed | — |
| ../{repo}-issue-55 | #55 Add tests | issue-55-add-tests | Clean | PR #78 (OPEN) |

### Suggestions
- **#42**: Has uncommitted work — commit or stash before switching
- **#55**: PR is open — check for reviews, then `/flow:merge`
```

### Step 6: Detect Stale Branches

Check for local branches that may need cleanup:

```bash
# Count local issue-* branches with no active worktree
WORKTREE_BRANCHES=$(git worktree list --porcelain | grep "^branch " | sed 's|branch refs/heads/||')
STALE_COUNT=0
for branch in $(git branch | grep 'issue-' | sed 's/^[ *]*//'); do
    echo "$WORKTREE_BRANCHES" | grep -q "^${branch}$" && continue
    STALE_COUNT=$((STALE_COUNT + 1))
done

# Check for prunable worktree references
PRUNABLE=$(git worktree list --porcelain | grep -c "prunable" || echo "0")
```

If stale branches or prunable references exist, append to output:

```markdown
### Cleanup Available
- {N} local issue branches with no active worktree
- {M} stale worktree references

Run `/flow:cleanup` to remove stale branches and references.
```

## Notes

- Worktrees on `main` or non-issue branches are listed but marked as "(not issue-linked)"
- If no worktrees exist besides main, report "No active worktrees. Run `/flow:start <issue>` to begin."
- Keep output concise — this is a quick status check
- Stale branch detection helps identify cleanup opportunities
