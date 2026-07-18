# Flow: Start Working on an Issue

Create a worktree and branch for a GitHub issue. Stateless - all context from git and GitHub.

Worktree mechanics ride Claude Code's **native worktrees**: the `EnterWorktree`
tool creates a checkout under `.claude/worktrees/<name>` on a new branch (base
governed by the `worktree.baseRef` setting - `fresh`, the default, branches from
`origin/<default-branch>`, matching the old `origin/main` behavior) and switches
the session into it. The issue-anchored `issue-<N>-<slug>` branch name is the
policy CPP keeps and enforces; it is not absorbed by the native tool.

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

`/flow:start` operates on the SESSION cwd's repo - `EnterWorktree` cannot create
a worktree in any other checkout, so invoke it from within the target repo. To
drive an issue in a repo the session did not start in, use
`/flow:auto <ISSUE> <PROJECT>`, whose Step 1 resolves the target checkout and
rides the deterministic git-worktree lane instead (issue #578).

### Step 2: Fetch Issue Details

```bash
ISSUE_NUM="$1"
gh issue view "$ISSUE_NUM" --json number,title,state,body
```

- If issue is not OPEN, warn the user and ask whether to proceed
- Extract the title for branch naming

### Step 3: Derive Branch and Worktree Names

```bash
# Sanitize title: lowercase, replace non-alphanum with hyphens, truncate.
# The cut -c1-64 keeps the name within the EnterWorktree 64-char limit.
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | cut -c1-50)

BRANCH="issue-${ISSUE_NUM}-${SLUG}"
```

The native worktree lives under `.claude/worktrees/${BRANCH}` - you do not choose
a sibling directory; pass `${BRANCH}` as the worktree `name` and the tool places
and names it.

**Worktree base override (issue #584, ADR 0003 Option A):** when
`FLOW_WORKTREE_BASE` is set (host config, e.g. `~/.bashrc`), worktrees are
created OUT of the repo at `$FLOW_WORKTREE_BASE/<repo>-<branch>` via plain
`git worktree add` + `cd` instead of `EnterWorktree` - the native tool's base
dir is not configurable, and `EnterWorktree(path=...)` outside the repo
triggers an approval prompt permission rules cannot suppress. Unset (the
shipped default), behavior below is byte-identical to today. Cleanup of a
base-override worktree is the git fallback (`/flow:merge` / `/flow:cleanup` /
`scripts/worktree-remove.sh` - all already layout-aware).

### Step 4: Check for Existing Work

```bash
# Check if already on the issue's branch (do NOT re-create in that case)
CURRENT_BRANCH=$(git branch --show-current)

# Check if a worktree already exists for this issue
git worktree list | grep "issue-${ISSUE_NUM}"

# Check if a remote branch exists (cross-machine pickup)
git fetch origin
git branch -r | grep "issue-${ISSUE_NUM}-"
```

Pick exactly one path:

- **Already on the issue branch** (`$CURRENT_BRANCH` matches `issue-${ISSUE_NUM}-`):
  verify you are NOT on main/master and use the current directory. Do nothing else.
- **Worktree already exists** (from a prior session): enter it with the
  `EnterWorktree` tool using its existing path (do NOT create a new one):
  `EnterWorktree(path="<path from git worktree list>")`.
- **Remote branch exists, no local worktree** (cross-machine pickup): the native
  tool cannot check out an existing remote branch, so add the worktree with git,
  then switch into it with `EnterWorktree`:
  ```bash
  REMOTE_BRANCH=$(git branch -r | grep "issue-${ISSUE_NUM}-" | head -1 | xargs)
  LOCAL_BRANCH="${REMOTE_BRANCH#origin/}"
  if [ -n "$FLOW_WORKTREE_BASE" ]; then
      mkdir -p "$FLOW_WORKTREE_BASE"
      WT_PATH="${FLOW_WORKTREE_BASE}/$(basename "$(git rev-parse --show-toplevel)")-${LOCAL_BRANCH}"
  else
      WT_PATH=".claude/worktrees/${LOCAL_BRANCH}"
  fi
  git worktree add -b "$LOCAL_BRANCH" "$WT_PATH" "$REMOTE_BRANCH"
  ```
  then call `EnterWorktree(path="$WT_PATH")` - or, when `FLOW_WORKTREE_BASE` is
  set, `cd "$WT_PATH"` instead (out-of-repo `EnterWorktree(path=...)` prompts;
  see the base-override note in Step 3).
- **Neither exists** (fresh start): create and enter the worktree natively by
  calling the `EnterWorktree` tool with `name="${BRANCH}"`. This branches from
  `origin/<default-branch>` (under the default `worktree.baseRef: fresh`) and
  switches the session into `.claude/worktrees/${BRANCH}`. Do NOT shell out to
  `git worktree add` for the fresh path. If your `worktree.baseRef` is set to
  `head`, sync `main` first so the branch does not start from a stale local HEAD.

  **Base-override exception (issue #584):** when `FLOW_WORKTREE_BASE` is set,
  the fresh path is the git lane instead of `EnterWorktree`:
  ```bash
  git fetch origin --quiet
  DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)
  DEFAULT_BRANCH=${DEFAULT_BRANCH#origin/}
  DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}
  mkdir -p "$FLOW_WORKTREE_BASE"
  WT_PATH="${FLOW_WORKTREE_BASE}/$(basename "$(git rev-parse --show-toplevel)")-${BRANCH}"
  git worktree add -b "$BRANCH" "$WT_PATH" "origin/${DEFAULT_BRANCH}"
  cd "$WT_PATH"
  ```

### Step 5: Verify, Normalize Branch, Output

**CRITICAL: Verify you are in the worktree, not on main/master.**

```bash
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    echo "ERROR: Still on main/master. EnterWorktree did not switch the session."
    exit 1
fi
```

**Enforce the issue-anchored branch name (the moat).** Native worktree creation
derives the branch from the worktree name; if the resulting branch is not exactly
`issue-${ISSUE_NUM}-${SLUG}`, rename it so every downstream step (`/flow:merge`,
`/flow:status`, `/flow:cleanup`) can extract the issue number from the branch:

```bash
if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
    git branch -m "$BRANCH"
    CURRENT_BRANCH="$BRANCH"
fi
echo "Verified: on branch '$CURRENT_BRANCH' in $(pwd)"
```

**Worktree path-resolution rule (issue #486).** A native `EnterWorktree` session
edits the worktree, but the worktree lives *inside* the main repo at
`.claude/worktrees/<name>/`. When you edit files from here, resolve paths from the
worktree root - `git rev-parse --show-toplevel` - or use plain relative paths from
the session cwd; never hand-build a `.claude/worktrees/<name>/...` absolute path,
which has been observed to land the edit in the MAIN repo working tree instead.
`/flow:auto` verifies this with `scripts/flow-worktree-guard.sh` before commit.

Report to the user:

```
Created worktree for issue #42: "Fix login bug"

  Directory: .claude/worktrees/issue-42-fix-login-bug
  Branch:    issue-42-fix-login-bug
  Verified:  Working directory is now the worktree (not main)
```

## Error Handling

- **Issue not found:** `gh issue view` fails → report "Issue #N not found"
- **Issue closed:** Warn but allow user to proceed (they may want to reopen)
- **Worktree exists:** Report existing path, do not error
- **Branch name collision:** Append short hash if needed
- **Not in a git repo:** Report error clearly

## Idempotency

Running `/flow:start 42` when the worktree already exists should detect it and report the path, not error or create a duplicate.
