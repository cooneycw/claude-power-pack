---
description: Diagnose flow workflow setup and environment
allowed-tools: Bash(git:*), Bash(gh:*), Bash(command:*), Bash(test:*), Bash(ls:*), Bash(readlink:*), Bash(grep:*), Bash(make:*), Read
---

# Flow: Doctor — Diagnose Workflow Environment

Check that the environment is properly configured for the `/flow` workflow.

## Instructions

When the user invokes `/flow:doctor`, run all diagnostic checks and present a single report.

### Step 1: Environment Prerequisites

Check required tools:

```bash
# git
git --version 2>/dev/null && echo "PASS" || echo "FAIL"

# gh CLI
gh --version 2>/dev/null && echo "PASS" || echo "FAIL"

# gh authentication
gh auth status 2>/dev/null && echo "PASS" || echo "FAIL"

# uv (optional but recommended)
uv --version 2>/dev/null || echo "NOT_FOUND"
```

### Step 2: Git Repository State

```bash
# In a git repository?
git rev-parse --show-toplevel 2>/dev/null || echo "NOT_A_REPO"

# Remote origin configured?
git remote get-url origin 2>/dev/null || echo "NO_REMOTE"

# Default branch
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'

# User identity
git config user.name 2>/dev/null || echo "NOT_SET"
git config user.email 2>/dev/null || echo "NOT_SET"
```

### Step 3: Makefile Targets

```bash
# Makefile exists?
if [ -f "Makefile" ]; then
  # List standard targets (lint, test, deploy, format, etc.)
  grep -E '^[a-zA-Z_-]+:' Makefile | sed 's/:.*//' | sort
else
  echo "NO_MAKEFILE"
fi
```

Report which of these standard targets exist: `lint`, `test`, `format`, `deploy`.

### Step 4: Hooks Configuration

```bash
# hooks.json exists?
if [ -f ".claude/hooks.json" ]; then
  # Check for expected hooks
  grep -l "SessionStart\|PreToolUse\|PostToolUse" .claude/hooks.json
fi
```

Check for the three expected hook types:
- **SessionStart**: Upstream change detection
- **PreToolUse (Bash)**: Dangerous command blocking via `hook-validate-command.sh`
- **PostToolUse (Bash/Read)**: Secret masking via `hook-mask-output.sh`

### Step 5: Scripts Availability

Check that core scripts exist in `~/.claude/scripts/`:

```bash
for script in prompt-context.sh worktree-remove.sh hook-mask-output.sh hook-validate-command.sh secrets-mask.sh; do
  if [ -x "$HOME/.claude/scripts/$script" ]; then
    echo "PASS $script"
  elif [ -f "$HOME/.claude/scripts/$script" ]; then
    echo "WARN $script (not executable)"
  else
    echo "FAIL $script"
  fi
done
```

### Step 6: Active Worktrees

```bash
git worktree list
```

For each worktree (skip main), check:
- Branch name and linked issue number
- Uncommitted changes (`git -C <path> status --porcelain | wc -l`)
- Unpushed commits (`git -C <path> rev-list --count origin/main..HEAD 2>/dev/null`)

### Step 7: GitHub Integration

```bash
# Can list issues?
gh issue list --limit 1 --json number 2>/dev/null && echo "PASS" || echo "FAIL"

# Can list PRs?
gh pr list --limit 1 --json number 2>/dev/null && echo "PASS" || echo "FAIL"
```

### Step 8: Generate Report

Output a single diagnostic report in this format:

```markdown
## Flow Doctor — {repo}

### Environment

| Check | Status | Details |
|-------|--------|---------|
| git | ✅ | v2.43.0 |
| gh CLI | ✅ | v2.62.0 |
| gh auth | ✅ | Logged in as {user} |
| uv | ✅ | v0.5.14 |

### Repository

| Check | Status | Details |
|-------|--------|---------|
| Git repo | ✅ | claude-power-pack |
| Remote | ✅ | github.com/cooneycw/claude-power-pack |
| User identity | ✅ | {name} <{email}> |

### Workflow Readiness

| Check | Status | Details |
|-------|--------|---------|
| Makefile | ✅/⚠️/❌ | Targets: lint, test, deploy / Not found |
| hooks.json | ✅/❌ | 3 hooks configured / Not found |
| validate-command hook | ✅/❌ | ~/.claude/scripts/hook-validate-command.sh |
| mask-output hook | ✅/❌ | ~/.claude/scripts/hook-mask-output.sh |
| prompt-context.sh | ✅/❌ | Shell prompt context |
| worktree-remove.sh | ✅/❌ | Safe worktree removal |
| secrets-mask.sh | ✅/❌ | Output masking filter |

### Active Worktrees

| Worktree | Issue | Branch | Status |
|----------|-------|--------|--------|
| ../{repo}-issue-42 | #42 | issue-42-fix-auth | 3 dirty, 1 unpushed |
| ../{repo}-issue-55 | #55 | issue-55-add-tests | Clean |

*No worktrees* → "No active worktrees. Run `/flow:start <issue>` to begin."

### GitHub Integration

| Check | Status |
|-------|--------|
| List issues | ✅/❌ |
| List PRs | ✅/❌ |

### Actions Needed

(Only if there are failures or warnings)

1. ❌ **Makefile missing** — Create a Makefile with `lint`, `test`, and `deploy` targets for `/flow:finish` and `/flow:deploy`
2. ❌ **worktree-remove.sh not found** — Run: `ln -sf ~/Projects/claude-power-pack/scripts/worktree-remove.sh ~/.claude/scripts/`
3. ⚠️ **uv not installed** — Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`

*All checks passed!* → "Environment is ready for `/flow` workflow."
```

## Status Symbols

- ✅ = Check passed
- ⚠️ = Optional/non-critical issue
- ❌ = Required check failed — action needed

## Notes

- This is a read-only diagnostic — it never modifies anything
- `uv` is recommended but not required (⚠️ if missing, not ❌)
- Makefile is recommended but not required (⚠️ if missing)
- Scripts and hooks are ❌ if missing since they provide security protection
- Keep the report concise — one table per section, actions at the end
