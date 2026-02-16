# Flow: Start Working on an Issue

Create a worktree and branch for a GitHub issue. Stateless — all context from git and GitHub.

## Arguments

- `ISSUE` (required): GitHub issue number (e.g., `42`)

## Instructions

When the user invokes `/flow:start <ISSUE>`, perform these steps:

### Step 1: Validate Prerequisites

```bash
# Ensure gh is authenticated
gh auth status

# Ensure we're in a git repo
git rev-parse --show-toplevel
```

### Step 2: Fetch Issue Details

```bash
ISSUE_NUM="$1"
gh issue view "$ISSUE_NUM" --json number,title,state,body
```

- If issue is not OPEN, warn the user and ask whether to proceed
- Extract the title for branch naming

### Step 3: Derive Branch and Worktree Names

```bash
REPO=$(basename "$(git rev-parse --show-toplevel)")

# Sanitize title: lowercase, replace non-alphanum with hyphens, truncate
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | cut -c1-50)

BRANCH="issue-${ISSUE_NUM}-${SLUG}"
WORKTREE_DIR="../${REPO}-issue-${ISSUE_NUM}"
```

### Step 4: Check for Existing Work

```bash
# Check if worktree already exists
git worktree list | grep "issue-${ISSUE_NUM}"

# Check if remote branch exists (cross-machine pickup)
git fetch origin
git branch -r | grep "issue-${ISSUE_NUM}-"
```

- **If worktree exists:** Inform user of the path. Do not recreate.
- **If remote branch exists (no local worktree):** Create worktree tracking the remote branch:
  ```bash
  REMOTE_BRANCH=$(git branch -r | grep "issue-${ISSUE_NUM}-" | head -1 | xargs)
  LOCAL_BRANCH="${REMOTE_BRANCH#origin/}"
  git worktree add -b "$LOCAL_BRANCH" "$WORKTREE_DIR" "$REMOTE_BRANCH"
  ```
- **If neither exists:** Create fresh:
  ```bash
  git fetch origin main
  git worktree add -b "$BRANCH" "$WORKTREE_DIR" origin/main
  ```

### Step 5: Output

Report to the user:

```
Created worktree for issue #42: "Fix login bug"

  Directory: ../my-project-issue-42
  Branch:    issue-42-fix-login-bug

  To start working:  cd ../my-project-issue-42
```

## Error Handling

- **Issue not found:** `gh issue view` fails → report "Issue #N not found"
- **Issue closed:** Warn but allow user to proceed (they may want to reopen)
- **Worktree exists:** Report existing path, do not error
- **Branch name collision:** Append short hash if needed
- **Not in a git repo:** Report error clearly

## Idempotency

Running `/flow:start 42` when the worktree already exists should detect it and report the path, not error or create a duplicate.
