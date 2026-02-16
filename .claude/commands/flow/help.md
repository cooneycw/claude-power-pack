# Flow Commands

Streamlined worktree-based development workflow. No locks, no Redis — just git.

## Commands

| Command | Purpose |
|---------|---------|
| `/flow:start <issue>` | Create worktree and branch from a GitHub issue |
| `/flow:status` | Show all active worktrees with issue/PR state |
| `/flow:finish` | Run quality gates, commit, push, and create PR |
| `/flow:merge` | Merge PR, clean up worktree and branch |
| `/flow:deploy [target]` | Run Makefile deploy target |
| `/flow:auto <issue>` | Full lifecycle: start → analyze → implement → finish → merge → deploy |
| `/flow:doctor` | Diagnose workflow environment and readiness |
| `/flow:help` | This help page |

## The Golden Path

```
/flow:auto 42
  ↓
  start → analyze → implement → finish → merge → deploy
```

Or step by step:
```
/flow:start 42  →  work  →  /flow:finish  →  /flow:merge  →  /flow:deploy
```

## Conventions

- **Worktree directory:** `../{repo}-issue-{N}` (sibling to main repo)
- **Branch name:** `issue-{N}-{slug}` (derived from issue title)
- **Commit style:** `type(scope): Description (Closes #N)`
- **All context is derived from git** — no external state tracking

## Quick Examples

```bash
# Start working on issue #42
/flow:start 42
# → Creates worktree ../my-project-issue-42
# → Branch: issue-42-fix-login-bug

# Check what's active
/flow:status
# → Shows worktrees, dirty state, PR status

# Done coding — push and create PR
/flow:finish
# → Runs make test/lint if available
# → Commits, pushes, creates PR

# PR approved — merge and clean up
/flow:merge
# → Merges PR, deletes branch, removes worktree

# Deploy to production
/flow:deploy
# → Runs make deploy

# Or do it all in one shot (start to deploy):
/flow:auto 42
# → start → analyze → implement → finish → merge → deploy
```
