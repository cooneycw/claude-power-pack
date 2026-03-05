# Flow Commands

Streamlined worktree-based development workflow. No locks, no Redis — just git.

## Commands

| Command | Purpose |
|---------|---------|
| `/flow:start <issue>` | Create worktree and branch from a GitHub issue |
| `/flow:status` | Show all active worktrees with issue/PR state |
| `/flow:check` | Run quality checks (lint, test, security) without committing |
| `/flow:finish` | Run quality gates, commit, push, and create PR |
| `/flow:merge` | Merge PR, clean up worktree and branch |
| `/flow:deploy [target]` | Run Makefile deploy target |
| `/flow:sync` | Push WIP branch to remote for cross-machine pickup |
| `/flow:auto <issue>` | Full lifecycle: start → analyze → implement → finish → merge → deploy |
| `/flow:cleanup` | Prune stale worktree references and delete merged branches |
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
/flow:start 42  →  work  →  /flow:check  →  /flow:finish  →  /flow:merge  →  /flow:deploy
```

Cross-machine (optional):
```
Machine A: /flow:start 42  →  work  →  /flow:sync
Machine B: /flow:start 42  →  picks up remote branch  →  continue working
```

## Security Gates

`/flow:finish` and `/flow:deploy` run automatic security scans as quality gates. Gate behavior is controlled by `.claude/security.yml`:

| Severity | `/flow:finish` (default) | `/flow:deploy` (default) |
|----------|--------------------------|--------------------------|
| CRITICAL | **Blocks** — must fix before PR | **Blocks** — must fix before deploy |
| HIGH | **Warns** — shows findings, proceeds | **Blocks** — must fix before deploy |
| MEDIUM | Passes | **Warns** — shows findings, proceeds |
| LOW | Passes | Passes |

**What happens when blocked:**
- The flow stops and displays all blocking findings with remediation hints
- You fix the issue, then re-run `/flow:finish` or `/flow:deploy`
- To suppress known false positives, add entries to `.claude/security.yml` `suppressions:`

**Configuration** (`.claude/security.yml`):
```yaml
gates:
  flow_finish:
    block_on: [critical]       # Severities that stop the flow
    warn_on: [high]            # Severities shown as warnings
  flow_deploy:
    block_on: [critical, high]
    warn_on: [medium]
suppressions:
  - id: HARDCODED_SECRET       # Finding type to suppress
    path: tests/fixtures/.*    # Regex for file path (optional)
    reason: "Test fixtures with fake credentials"
```

If no `.claude/security.yml` exists, the defaults above are used. If `lib/security` is not available, the gate is skipped with a warning.

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

# Pre-flight check (lint + test + security, no commit)
/flow:check
# → Reports pass/fail per check

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

# Sync WIP to remote (for cross-machine work)
/flow:sync
# → Auto-commits WIP, pushes branch to origin

# Or do it all in one shot (start to deploy):
/flow:auto 42
# → start → analyze → implement → finish → merge → deploy
```
