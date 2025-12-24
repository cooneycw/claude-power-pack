# Issue-Driven Development & Worktrees

*From Claude Code Best Practices - r/ClaudeCode community wisdom*

## What is Issue-Driven Development?

Issue-Driven Development (IDD) is a workflow pattern that combines:
- **Hierarchical Issues** - Phases → Waves → Micro-issues
- **Git Worktrees** - Parallel development without branch switching
- **Terminal Labeling** - Visual context for multiple sessions
- **Structured Commits** - Traceable, closeable commits via "Closes #N"

## The Three-Level Hierarchy

```
Phase (Epic)
├── Wave (Feature Group)
│   ├── Micro-Issue (Atomic Task)
│   └── Micro-Issue
└── Wave
    └── Micro-Issue
```

## Why It Works with Claude Code

| Problem | IDD Solution |
|---------|--------------|
| Feature too large | Break into micro-issues |
| Lost context | Each issue has acceptance criteria |
| Parallel work blocked | Git worktrees enable concurrent development |
| No traceability | Commits link to issues via "Closes #N" |

## Key Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Branch | `issue-{N}-{description}` | `issue-123-player-landing` |
| Worktree | `{repo}-issue-{N}` | `nhl-api-issue-123` |
| Commit | `type(scope): Desc (Closes #N)` | `feat(api): Add endpoint (Closes #42)` |

## Shell Prompt Context

When running multiple Claude Code sessions across worktrees, knowing which issue you're working on is critical.

**Setup (add to `~/.bashrc`):**
```bash
ln -sf ~/Projects/claude-power-pack/scripts/prompt-context.sh ~/.claude/scripts/
export PS1='$(~/.claude/scripts/prompt-context.sh)\w $ '
```

**Result:**
```bash
# In worktree on branch issue-42-auth-flow
[NHL #42] ~/Projects/nhl-api-issue-42 $

# On main branch
[NHL] ~/Projects/nhl-api $
```

## Worktree Commands

```bash
# Create worktree for issue
git worktree add -b issue-42-auth ../project-issue-42

# List worktrees
git worktree list

# Remove worktree (use script for safety)
~/.claude/scripts/worktree-remove.sh ../project-issue-42 --delete-branch
```

## Getting Started

Use the `/project-next` command to analyze your repository's issues and get prioritized recommendations for what to work on next.

## Multi-Session Workflow

With tmux + worktrees:

1. **Session 1:** Main repo - planning, PR review
2. **Session 2:** Worktree for Issue #42 - frontend work
3. **Session 3:** Worktree for Issue #43 - backend work

Each session has its own context, no branch switching needed.

## Related Resources

- `ISSUE_DRIVEN_DEVELOPMENT.md` - Complete methodology guide
- `/project-next` - Issue prioritization command
- `/project-lite` - Quick project reference

---

*Triggers: issue driven, worktree, IDD, parallel development, git worktree*
