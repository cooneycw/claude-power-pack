# Issue-Driven Development with Claude Code

A methodology for managing complex projects through hierarchical issues, git worktrees, and Claude Code sessions.

---

## Overview

Issue-Driven Development (IDD) is a workflow pattern that emerged from managing large projects with Claude Code. It combines:

- **Hierarchical Issue Structure** - Phases, Waves, and Micro-issues
- **Git Worktrees** - Parallel development without branch switching
- **Shell Prompt Context** - Visual context for current worktree
- **Structured Commit Patterns** - Traceable, closeable commits

This guide documents the methodology as practiced in real-world projects with 100+ issues.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Issue Hierarchy](#issue-hierarchy)
3. [Micro-Issue Anatomy](#micro-issue-anatomy)
4. [Git Worktree Workflow](#git-worktree-workflow)
5. [Shell Prompt Context](#shell-prompt-context)
6. [Commit Conventions](#commit-conventions)
7. [Flow Workflow](#flow-workflow)
8. [Multi-Agent Coordination](#multi-agent-coordination)
9. [Example Workflow](#example-workflow)
10. [Best Practices](#best-practices)
11. [Anti-Patterns](#anti-patterns)
12. [Quick Reference](#quick-reference)

---

## Core Concepts

### Why Issue-Driven Development?

Claude Code works best with clear, bounded tasks. Large features overwhelm context and lead to:
- Incomplete implementations
- Forgotten edge cases
- Difficult code review
- Context degradation over long sessions

IDD addresses this by breaking work into atomic, testable units:

| Problem | IDD Solution |
|---------|--------------|
| Feature too large | Break into micro-issues |
| Lost context | Each issue has acceptance criteria |
| Parallel work blocked | Git worktrees enable concurrent development |
| Unknown dependencies | Issues explicitly declare blockers |
| No traceability | Commits link to issues via "Closes #N" |

### The Three-Level Hierarchy

```
Phase (Epic)
├── Wave (Feature Group)
│   ├── Micro-Issue (Atomic Task)
│   ├── Micro-Issue
│   └── Micro-Issue
└── Wave
    ├── Micro-Issue
    └── Micro-Issue
```

---

## Issue Hierarchy

### Phase (Epic Level)

**Purpose**: High-level project milestone
**Scope**: Weeks to months
**Example**: "Phase 2: Core Implementation Plan" (#25)

**Contains**:
- Multiple Waves
- No direct implementation
- Strategic planning and architecture decisions
- Success criteria for the phase

### Wave (Feature Group)

**Purpose**: Cohesive set of related functionality
**Scope**: Days to 1-2 weeks
**Example**: "Wave 7: Download Orchestration & Persistence" (#92)

**Structure**:
```markdown
## Wave N: Feature Name

**Parent Issue:** #XX (Phase Reference)

---

## Overview
Brief description of what this wave accomplishes.

## Current State
- What works
- What's missing

## Issue Breakdown

| Issue | Title | Status |
|-------|-------|--------|
| #101 | Micro-issue 1 | Closed |
| #102 | Micro-issue 2 | Open |
| #103 | Micro-issue 3 | Open |

## Dependencies
- Requires Wave N-1 to be complete
- Blocks Wave N+1
```

### Micro-Issue (Atomic Task)

**Purpose**: Single, implementable unit of work
**Scope**: 1-4 hours of focused work
**Example**: "Wave 5c.1: Base NHL Stats Downloader Infrastructure" (#115)

**Key Properties**:
- Self-contained with all context needed
- Clear acceptance criteria
- Testable outcomes
- Explicit dependencies

---

## Micro-Issue Anatomy

Every micro-issue follows a consistent template:

### Required Sections

```markdown
## Wave X.Y: Descriptive Title

**Parent Issue:** #XX (Wave Reference)

---

## Overview
1-3 sentences describing what this issue accomplishes.

---

## Files to Create/Modify

- `src/module/file.py` - Purpose
- `tests/test_file.py` - Test coverage

---

## Implementation

```python
# Code stubs or key interfaces
class MyClass:
    def method(self) -> ReturnType:
        """Docstring explaining behavior."""
        pass
```

---

## Acceptance Criteria

- [ ] Criterion 1: Specific, testable requirement
- [ ] Criterion 2: Another requirement
- [ ] Unit tests pass with >80% coverage
- [ ] Code follows project conventions
- [ ] Pre-commit hooks pass

---

## Depends On

- #XXX (blocking issue)
- None (if first issue in chain)

## Blocks

- #XXX (dependent issue)

---

## Complexity: LOW | MEDIUM | HIGH
```

### Key Principles

1. **Self-Contained** - Everything needed to implement is in the issue
2. **Testable** - Acceptance criteria are verifiable
3. **Bounded** - Can complete in one Claude Code session
4. **Traceable** - Links to parent and sibling issues
5. **Actionable** - Clear next steps, no ambiguity

---

## Git Worktree Workflow

### What Are Worktrees?

Git worktrees allow multiple branches to be checked out simultaneously in different directories. They share the same `.git` database but have independent working directories.

```
/Projects/
├── my-project/              # Main repo (main branch)
│   └── .git/                # Shared git database
│
├── my-project-issue-42/     # Worktree (issue-42-feature branch)
│   └── .git -> ../my-project/.git
│
└── my-project-issue-57/     # Worktree (issue-57-bugfix branch)
    └── .git -> ../my-project/.git
```

### Naming Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Branch | `issue-{number}-{short-description}` | `issue-123-player-landing` |
| Worktree | `{repo}-issue-{number}` | `nhl-api-issue-123` |

### Worktree Commands

**Create worktree for an issue:**
```bash
cd /path/to/main-repo
git worktree add -b issue-{N}-{description} ../repo-issue-{N}
cd ../repo-issue-{N}
```

**List all worktrees:**
```bash
git worktree list
```

**Remove after merge:**
```bash
# IMPORTANT: cd to main repo FIRST to avoid breaking the shell
cd /path/to/main-repo
git worktree remove ../repo-issue-{N}
git branch -d issue-{N}-{description}
```

> ⚠️ **Shell CWD Warning:** Always `cd` to the main repo before removing a worktree. If your shell's current working directory is inside the worktree being removed, the shell will break and no further commands will work. Using `git -C /path/to/main-repo worktree remove` does NOT protect against this—only changing the shell's cwd does.

**Prune stale worktrees:**
```bash
git worktree prune
```

### Why Worktrees?

| Without Worktrees | With Worktrees |
|-------------------|----------------|
| `git stash` / `git checkout` | cd to different directory |
| One issue at a time | Multiple issues in parallel |
| Context switching overhead | Independent Claude sessions |
| Lost WIP on branch switch | All work preserved |
| Sequential development | Parallel development |

---

## Shell Prompt Context

### Why Prompt Context Matters

When running multiple Claude Code sessions across worktrees, knowing which issue you're working on is critical. Shell prompt integration provides always-visible context.

### Setup

**Install and configure the prompt-context script:**

Add to `~/.bashrc`:
```bash
# Symlink the script
mkdir -p ~/.claude/scripts
ln -sf ~/Projects/claude-power-pack/scripts/prompt-context.sh ~/.claude/scripts/

# Add to PS1
export PS1='$(~/.claude/scripts/prompt-context.sh)\w $ '
```

For Zsh (`~/.zshrc`):
```zsh
precmd() { PS1="$(~/.claude/scripts/prompt-context.sh)%~ %% " }
```

### How It Works

The script automatically detects:
1. **Project prefix** from `.claude-prefix` file or derives from repo name
2. **Issue number** from branch name (pattern: `issue-{N}-*`)

### Example

```bash
# In worktree on branch issue-42-auth-flow
[NHL #42] ~/Projects/nhl-api-issue-42 $

# In main repo on main branch
[NHL] ~/Projects/nhl-api $

# Not in a git repo
~/Downloads $
```

### Customization

Create `.claude-prefix` in project root to set custom prefix:
```bash
echo "NHL" > .claude-prefix
```

Otherwise, prefix is derived from repo name:
- `nhl-api` → `NHL`
- `claude-power-pack` → `CPP`
- `my-django-app` → `MDA`

---

## Commit Conventions

### Format

```
type(scope): Description (Closes #N)

Optional longer description explaining the change.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### Types

| Type | When to Use |
|------|-------------|
| `feat` | New functionality |
| `fix` | Bug fixes |
| `refactor` | Code restructuring (no behavior change) |
| `test` | Adding/updating tests |
| `docs` | Documentation only |
| `chore` | Maintenance tasks |
| `ci` | CI/CD changes |

### Scope Examples

- `feat(downloader)` - Downloader-related feature
- `fix(viewer)` - Viewer bug fix
- `test(integration)` - Integration test changes
- `docs(readme)` - README updates

### Closing Issues

Using `(Closes #N)` in commit messages:
1. Automatically closes the issue when PR merges
2. Creates bidirectional link between commit and issue
3. Updates project tracking automatically

**Example:**
```bash
git commit -m "$(cat <<'EOF'
feat(downloader): Add player landing persistence (Closes #123)

Implements database persistence for player landing data.
- Adds persist() method to PlayerLandingDownloader
- Creates player records in database
- Handles upsert for existing players

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Flow Workflow

### The Golden Path

The `/flow` command set provides a stateless, git-native workflow for the full issue lifecycle:

```
/flow:start 42 → work → /flow:finish → /flow:merge → /flow:deploy
```

Or automate the entire lifecycle in one shot:

```
/flow:auto 42
```

### Flow Commands

| Command | Purpose |
|---------|---------|
| `/flow:start <issue>` | Create worktree and branch for an issue |
| `/flow:status` | Show active worktrees with issue and PR status |
| `/flow:finish` | Run quality gates, commit, push, create PR |
| `/flow:merge` | Squash-merge PR, clean up worktree and branch |
| `/flow:deploy [target]` | Run `make deploy` (if Makefile target exists) |
| `/flow:sync` | Push WIP branch to remote for cross-machine pickup |
| `/flow:auto <issue>` | Full lifecycle: start → analyze → implement → finish → merge → deploy |
| `/flow:help` | Show all flow commands and conventions |

### How It Works

Flow commands are **stateless** — all context is derived from git (branches, worktrees, remotes) and GitHub (issues, PRs). No locking, no Redis, no coordination server needed.

- `/flow:start` creates a worktree from `origin/main`, or picks up an existing remote branch
- `/flow:sync` auto-commits WIP and pushes to remote for cross-machine pickup
- `/flow:finish` runs `make lint` and `make test` (if targets exist) before committing
- `/flow:merge` squash-merges the PR and safely removes the worktree
- `/flow:deploy` logs deployments to `.claude/deploy.log`

### Makefile Integration

Flow commands integrate with `make` targets for quality gates and deployment:

```makefile
# Quality gates (used by /flow:finish)
lint:
	ruff check .

test:
	pytest

# Deployment (used by /flow:deploy)
deploy:
	./scripts/deploy.sh
```

If a Makefile exists with `lint`, `test`, or `deploy` targets, flow commands use them automatically.

### Cross-Machine Workflow (Optional)

For users who work across multiple machines (e.g., desktop and laptop), `/flow:sync` provides lightweight git-based state transfer with no infrastructure required.

**How it works:**
```
Machine A: /flow:start 42  →  work  →  /flow:sync
  ↓ (git push)
Machine B: /flow:start 42  →  detects remote branch  →  continue working
```

**Detailed steps:**

1. **Machine A** — Start work as normal:
   ```bash
   /flow:start 42        # Creates worktree and branch
   # ... do some work ...
   /flow:sync             # Auto-commits WIP, pushes to origin
   ```

2. **Machine B** — Pick up where you left off:
   ```bash
   /flow:start 42        # Detects remote branch, creates worktree tracking it
   # ... continue working ...
   /flow:finish           # When done: lint, test, commit, push, PR
   ```

**Why WIP commits are safe:** `/flow:merge` uses squash-merge, so all intermediate commits (including WIP auto-commits from `/flow:sync`) are collapsed into a single clean commit on main.

**No configuration needed** — this works with any standard git remote. The sync is just `git push` and the pickup is just `git checkout --track`.

---

## Multi-Agent Coordination

### How Issues Enable Parallel Work

Each micro-issue serves as a **knowledge transfer document** for different Claude sessions:

1. **Context is in the issue** - No need to explain the task
2. **Acceptance criteria are clear** - No ambiguity about "done"
3. **Dependencies are explicit** - Know what to wait for
4. **Code stubs provided** - Expected interfaces are defined

### Coordination Pattern

```
Main Repo (planning)          Worktree 1 (issue-42)       Worktree 2 (issue-57)
     │                              │                           │
     │  ┌──────────────────────────┐│                           │
     │  │ Issue #42: Feature X     ││                           │
     │  │ - Acceptance criteria    ││                           │
     │  │ - Code stubs            ││                           │
     │  │ - Dependencies          ││                           │
     │  └──────────────────────────┘│                           │
     │                              │                           │
     │  Claude Session 1 ──────────►│                           │
     │  (reads issue, implements)   │                           │
     │                              │                           │
     │  ┌──────────────────────────┐│                           │
     │  │ Issue #57: Feature Y     ││                           │
     │  └──────────────────────────┘│                           │
     │                              │  Claude Session 2 ────────►
     │                              │  (reads issue, implements)
     │                              │                           │
     │◄─────────── PR #42 ──────────│                           │
     │◄───────────────────────────── PR #57 ───────────────────│
```

### Tips for Multi-Agent Work

1. **Write issues before starting sessions** - All context upfront
2. **Use `/project-next` to identify parallel work** - Find non-blocking issues
3. **Use `/flow:start N` to begin** - Creates isolated worktree per issue
4. **Use prompt context** - Visual confirmation of current worktree/issue
5. **Don't share worktrees between sessions** - One session per worktree
6. **Use `/flow:finish` to ship** - Handles commit, push, and PR creation

> **Note:** For teams needing distributed locking, optional Redis coordination is available in `extras/redis-coordination/`. See that directory's README for setup.

---

## Example Workflow

### Scenario: Implement Player Landing Persistence

**Issue:** Wave 7.2: Player Landing Downloader Persistence (#123)

#### Option A: Full Automation (Recommended)

```bash
/flow:auto 123
```

This runs the complete lifecycle: creates worktree → analyzes issue → implements → commits → creates PR → merges → cleans up.

#### Option B: Step-by-Step

**Step 1: Start**
```bash
/flow:start 123
```
Creates worktree at `../my-api-issue-123` with branch `issue-123-player-landing`.

**Step 2: Verify Prompt Context**
Your shell prompt now shows:
```bash
[MAP #123] ~/Projects/my-api-issue-123 $
```

**Step 3: Implement**
- Follow acceptance criteria in issue
- Write tests first (TDD encouraged)
- Commit frequently with meaningful messages

**Step 4: Finish (commit, push, PR)**
```bash
/flow:finish
```
Runs `make lint` and `make test` (if available), commits with conventional format, pushes, and creates PR.

**Step 5: Merge and Clean Up**
```bash
/flow:merge
```
Squash-merges the PR, removes worktree and branch, pulls main.

**Step 6: Deploy (optional)**
```bash
/flow:deploy
```
Runs `make deploy` if the target exists.

#### Option C: Manual Git (if you prefer)

<details>
<summary>Click to expand manual workflow</summary>

```bash
# Create worktree
cd /home/user/Projects/my-api
git worktree add -b issue-123-player-landing ../my-api-issue-123
cd ../my-api-issue-123

# Implement and commit
git commit -m "feat(downloader): Add player landing persistence (Closes #123)"

# Push and create PR
git push -u origin issue-123-player-landing
gh pr create --title "feat(downloader): Player landing persistence" --body "Closes #123"

# Cleanup (CRITICAL: cd to main repo FIRST)
cd /home/user/Projects/my-api
git worktree remove ../my-api-issue-123
git branch -d issue-123-player-landing
git pull
```

</details>

---

## Best Practices

### Issue Creation

1. **Write issues before code** - Spec-driven development
2. **Include code stubs** - Show expected interfaces
3. **Explicit dependencies** - Declare blockers upfront
4. **Testable criteria** - Every criterion should be verifiable
5. **Link parent issues** - Maintain hierarchy

### During Implementation

1. **One issue per session** - Focused context
2. **Reset sessions after commits** - Fresh context
3. **Use Plan Mode first** - Clarify before implementing
4. **Reference the issue** - Keep criteria visible
5. **Commit frequently** - Small, atomic commits

### Workflow

1. **Use `/flow:start N` to begin work** - Creates worktree automatically
2. **Use `/flow:finish` to ship** - Handles commit, push, PR creation
3. **Use `/flow:merge` to clean up** - Merges PR, removes worktree
4. **Use `/project-next`** - Get prioritized recommendations
5. **Don't start Claude from worktrees** - Start from main repo

---

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Giant issues | Context overflow | Break into micro-issues |
| No acceptance criteria | Unclear "done" | Add testable criteria |
| Starting Claude from worktree | Session breaks on cleanup | Start from main repo |
| Removing worktree without cd | Shell breaks (cwd deleted) | `cd` to main repo first, then remove |
| Multiple issues in one commit | Harder to revert | One issue per commit |
| Skipping cleanup | Branch clutter | Remove worktrees after merge |
| No parent references | Lost hierarchy | Always link to parent issue |
| Vague issue titles | Hard to find | Use "Wave X.Y: Specific Title" |
| Missing code stubs | Unclear interfaces | Provide expected signatures |

---

## Quick Reference

### Commands Cheat Sheet

```bash
# Flow Workflow (Recommended)
/flow:start 42                                     # Create worktree for issue
/flow:status                                       # Show active worktrees
/flow:finish                                       # Lint, test, commit, push, PR
/flow:merge                                        # Squash-merge PR, clean up
/flow:deploy                                       # Run make deploy
/flow:sync                                         # Push WIP to remote (cross-machine)
/flow:auto 42                                      # Full lifecycle in one shot
/flow:help                                         # Show all flow commands

# Manual Worktree Management
git worktree add -b issue-N-desc ../repo-issue-N   # Create
git worktree list                                   # List all
cd /path/to/main-repo && git worktree remove ../repo-issue-N  # Remove (cd first!)
git worktree prune                                 # Clean stale

# Shell Prompt Context (automatic - no commands needed)
# Prompt shows: [PREFIX #N] when on issue-N-* branch
# Customize prefix: echo "NHL" > .claude-prefix

# GitHub CLI
gh issue list --state open                         # List issues
gh issue view N                                    # View issue
gh issue create --title "..." --body "..."         # Create issue
gh pr create --title "..." --body "Closes #N"      # Create PR

# Git
git push -u origin issue-N-desc                    # Push branch
git branch -d issue-N-desc                         # Delete branch
```

### Issue Template Checklist

- [ ] Title: `Wave X.Y: Descriptive Title`
- [ ] Parent issue link
- [ ] Overview (1-3 sentences)
- [ ] Files to create/modify
- [ ] Code stubs or interfaces
- [ ] Acceptance criteria (testable)
- [ ] Dependencies (Depends On / Blocks)
- [ ] Complexity rating

### Commit Template

```
type(scope): Description (Closes #N)

[Optional body]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

## Related Documentation

- [Claude Code Best Practices](CLAUDE_CODE_BEST_PRACTICES_COMPREHENSIVE.md)
- [Progressive Disclosure Guide](PROGRESSIVE_DISCLOSURE_GUIDE.md)
- [Git Worktree Official Docs](https://git-scm.com/docs/git-worktree)
- [GitHub CLI Reference](https://cli.github.com/manual/)

---

*This methodology was developed through real-world usage on projects with 140+ issues and refined over months of Claude Code development.*
