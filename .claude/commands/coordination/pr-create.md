# Coordinated PR Creation

> **Requires:** `extras/redis-coordination/scripts/` installed to `~/.claude/scripts/`. See `extras/redis-coordination/README.md`.

Create a pull request with session locking to prevent duplicate PRs across concurrent sessions.

## Workflow

1. **Acquire Lock**
   - Lock name: `pr-{repo}-{branch}`
   - If lock held by another session, wait or fail based on config

2. **Check for Existing PR**
   - Run: `gh pr list --head $(git branch --show-current) --json number,url`
   - If PR exists, report URL and release lock

3. **Create PR**
   - Gather commit info: `git log origin/main..HEAD --oneline`
   - Draft PR with summary and test plan
   - Create using `gh pr create`

4. **Release Lock**
   - Always release lock, even on failure

## Instructions

When the user invokes `/coordination:pr-create`, perform these steps:

### Step 1: Check Prerequisites
```bash
# Ensure we're on a feature branch
BRANCH=$(git branch --show-current)
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    echo "ERROR: Cannot create PR from main/master branch"
    exit 1
fi

# Ensure we have commits to push
COMMITS=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")
if [[ "$COMMITS" == "0" ]]; then
    echo "ERROR: No commits to create PR from"
    exit 1
fi
```

### Step 2: Acquire Lock
```bash
REPO=$(basename $(git rev-parse --show-toplevel))
LOCK_NAME="pr-${REPO}-${BRANCH}"

~/.claude/scripts/session-lock.sh acquire "$LOCK_NAME" 120
```

If lock acquisition fails, inform the user which session holds the lock.

### Step 3: Check for Existing PR
```bash
EXISTING=$(gh pr list --head "$BRANCH" --json number,url --jq '.[0]')
if [[ -n "$EXISTING" ]]; then
    echo "PR already exists: $EXISTING"
    ~/.claude/scripts/session-lock.sh release "$LOCK_NAME"
    exit 0
fi
```

### Step 4: Push Branch (if needed)
```bash
# Ensure branch is pushed
if ! git ls-remote --exit-code origin "$BRANCH" >/dev/null 2>&1; then
    git push -u origin "$BRANCH"
fi
```

### Step 5: Create PR
Use standard PR creation workflow:
- Title: Conventional commit style (feat/fix/docs/etc.)
- Body: Summary of changes + Test Plan
- Include "Closes #N" if working on an issue

### Step 6: Release Lock
```bash
~/.claude/scripts/session-lock.sh release "$LOCK_NAME"
```

## Example Usage

```
User: /coordination:pr-create

Claude: I'll create a coordinated PR for this branch.

[Acquires lock pr-nhl-api-issue-170]
[Checks for existing PR - none found]
[Creates PR with summary]
[Releases lock]

PR created: https://github.com/cooneycw/nhl-api/pull/42
```

## Error Handling

- **Lock unavailable**: Report which session holds it and offer to wait or abort
- **PR already exists**: Report the existing PR URL
- **Push fails**: Release lock and report error
- **gh fails**: Release lock and report error

Always release the lock in finally/cleanup block.
