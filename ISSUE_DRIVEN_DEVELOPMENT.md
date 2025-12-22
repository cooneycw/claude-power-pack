# Issue-Driven Development with Claude Code

A methodology for managing complex projects through hierarchical issues, git worktrees, and Claude Code sessions.

---

## Overview

Issue-Driven Development (IDD) is a workflow pattern that emerged from managing large projects with Claude Code. It combines:

- **Hierarchical Issue Structure** - Phases, Waves, and Micro-issues
- **Git Worktrees** - Parallel development without branch switching
- **Terminal Labeling** - Visual context for multiple sessions
- **Structured Commit Patterns** - Traceable, closeable commits

This guide documents the methodology as practiced in real-world projects with 100+ issues.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Issue Hierarchy](#issue-hierarchy)
3. [Micro-Issue Anatomy](#micro-issue-anatomy)
4. [Git Worktree Workflow](#git-worktree-workflow)
5. [Terminal Labeling](#terminal-labeling)
6. [Commit Conventions](#commit-conventions)
7. [Multi-Agent Coordination](#multi-agent-coordination)
   - [Session Coordination](#session-coordination)
8. [Example Workflow](#example-workflow)
9. [Best Practices](#best-practices)
10. [Anti-Patterns](#anti-patterns)
11. [Quick Reference](#quick-reference)

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
cd /path/to/main-repo
git worktree remove ../repo-issue-{N}
git branch -d issue-{N}-{description}
```

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

## Terminal Labeling

### Why Terminal Labels Matter

When running multiple Claude Code sessions (especially with tmux or across worktrees), knowing which session handles which task is critical.

### Setup

**Install the terminal-label script:**
```bash
mkdir -p ~/.claude/scripts
ln -sf /path/to/claude-power-pack/scripts/terminal-label.sh ~/.claude/scripts/
```

**Set project prefix:**
```bash
~/.claude/scripts/terminal-label.sh prefix "MyProject"
```

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `terminal-label.sh set "Label"` | Set custom label | `terminal-label.sh set "Feature: Auth"` |
| `terminal-label.sh issue [PREFIX] NUM [TITLE]` | Set issue label | `terminal-label.sh issue 42 "Bug Fix"` |
| `terminal-label.sh project [PREFIX]` | Set project selection mode | `terminal-label.sh project NHL` |
| `terminal-label.sh await` | Set awaiting mode | (via hook) |
| `terminal-label.sh restore` | Restore saved label | (via hook) |
| `terminal-label.sh status` | Show configuration | Debug info |

### Hook Integration

Add to your `.claude/hooks.json`:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "~/.claude/scripts/session-register.sh start 2>/dev/null || true",
        "timeout": 5000
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/terminal-label.sh restore 2>/dev/null || true",
            "timeout": 1000
          },
          {
            "type": "command",
            "command": "~/.claude/scripts/session-heartbeat.sh touch 2>/dev/null || true",
            "timeout": 500
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/terminal-label.sh await 2>/dev/null || true",
            "timeout": 1000
          },
          {
            "type": "command",
            "command": "~/.claude/scripts/session-register.sh pause 2>/dev/null || true",
            "timeout": 1000
          }
        ]
      }
    ]
  }
}
```

### Workflow Example

```bash
# Terminal 1: Working on Issue #42
terminal-label.sh issue 42 "Auth Flow"
# Shows: "Issue #42: Auth Flow"

# Terminal 2: Working on Issue #57
terminal-label.sh issue 57 "API Refactor"
# Shows: "Issue #57: API Refactor"

# When Claude finishes responding:
# Shows: "Claude: Awaiting Input..."

# When you type next prompt:
# Shows: "Issue #42: Auth Flow" (restored)
```

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
3. **Label terminals with issue numbers** - Avoid confusion
4. **Don't share worktrees between sessions** - One session per worktree

### Session Coordination

With multiple sessions running on the same repository, conflicts can occur:

| Problem | Solution |
|---------|----------|
| Two sessions create PRs | Lock-based coordination |
| pytest runs interfere | Test suite locking |
| Sessions kill each other's work | Session registry + heartbeat |
| No visibility into active work | `/project-next` shows sessions |

**Coordination Scripts:**
```bash
# Check who's working on what
~/.claude/scripts/session-register.sh status

# View active locks
~/.claude/scripts/session-lock.sh list

# Run pytest with coordination
~/.claude/scripts/pytest-locked.sh -m unit

# Create PR with locking
/coordination:pr-create

# Merge to main with locking
/coordination:merge-main issue-123-feature
```

**How It Works:**

1. **Session Registration** - Each session registers at start, maintains heartbeat
2. **Lock Acquisition** - Operations acquire locks before executing
3. **Stale Detection** - Sessions without heartbeat for 60s are considered dead
4. **Auto-Release** - Dead session locks are automatically released

**Hooks Integration:**
- `SessionStart` → Registers session, sets terminal label
- `UserPromptSubmit` → Updates heartbeat timestamp
- `Stop` → Marks session as paused

See `~/.claude/coordination/` for lock files and session registry.

---

## Example Workflow

### Scenario: Implement Player Landing Persistence

**Issue:** Wave 7.2: Player Landing Downloader Persistence (#123)

**Step 1: Create Worktree**
```bash
cd /home/user/Projects/my-api
git worktree add -b issue-123-player-landing ../my-api-issue-123
cd ../my-api-issue-123
```

**Step 2: Set Terminal Label**
```bash
terminal-label.sh issue 123 "Player Landing"
```

**Step 3: Start Claude Code Session**
```bash
# IMPORTANT: Start from main repo, not worktree!
cd /home/user/Projects/my-api
claude
# Then navigate to worktree for implementation
```

**Step 4: Reference the Issue**
Tell Claude: "I'm working on issue #123. Please read the acceptance criteria and implement the feature."

**Step 5: Implement**
- Follow acceptance criteria in issue
- Write tests first (TDD encouraged)
- Commit frequently with meaningful messages

**Step 6: Final Commit**
```bash
git commit -m "$(cat <<'EOF'
feat(downloader): Add player landing persistence (Closes #123)

Implements database persistence for player landing data.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

**Step 7: Create PR**
```bash
git push -u origin issue-123-player-landing
gh pr create --title "feat(downloader): Player landing persistence" \
  --body "Closes #123"
```

**Step 8: Cleanup (after merge)**
```bash
cd /home/user/Projects/my-api
git worktree remove ../my-api-issue-123
git branch -d issue-123-player-landing
git pull
```

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

1. **Don't start Claude from worktrees** - Start from main repo
2. **Label terminals immediately** - Prevent confusion
3. **Close issues via commits** - Automatic tracking
4. **Clean up worktrees promptly** - Avoid stale branches
5. **Use `/project-next`** - Get prioritized recommendations

---

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Giant issues | Context overflow | Break into micro-issues |
| No acceptance criteria | Unclear "done" | Add testable criteria |
| Starting Claude from worktree | Session breaks on cleanup | Start from main repo |
| Multiple issues in one commit | Harder to revert | One issue per commit |
| Skipping cleanup | Branch clutter | Remove worktrees after merge |
| No parent references | Lost hierarchy | Always link to parent issue |
| Vague issue titles | Hard to find | Use "Wave X.Y: Specific Title" |
| Missing code stubs | Unclear interfaces | Provide expected signatures |

---

## Quick Reference

### Commands Cheat Sheet

```bash
# Worktree Management
git worktree add -b issue-N-desc ../repo-issue-N   # Create
git worktree list                                   # List all
git worktree remove ../repo-issue-N                # Remove
git worktree prune                                 # Clean stale

# Terminal Labels
terminal-label.sh issue N "Title"                  # Set issue label
terminal-label.sh project MyApp                    # Set project label
terminal-label.sh await                            # Awaiting mode
terminal-label.sh restore                          # Restore saved
terminal-label.sh status                           # Show config

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
