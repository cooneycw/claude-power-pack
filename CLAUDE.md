# Claude Power Pack

## Project Overview

This repository contains two main components:
1. **Claude Code Best Practices** - Community wisdom from r/ClaudeCode
2. **MCP Second Opinion Server** - Gemini-powered code review

## Quick References

- **Best Practices:** `CLAUDE_CODE_BEST_PRACTICES.md`
- **Issue-Driven Development:** `ISSUE_DRIVEN_DEVELOPMENT.md`
- **Progressive Disclosure:** `PROGRESSIVE_DISCLOSURE_GUIDE.md`
- **MCP Token Audit:** `MCP_TOKEN_AUDIT_CHECKLIST.md`
- **MCP Server Docs:** `mcp-second-opinion/`

## Key Conventions

- Python 3.11+
- Use conda environments for MCP server
- MCP server runs on port 8080
- All documentation uses progressive disclosure principles

## Repository Structure

```
claude-power-pack/
├── CLAUDE_CODE_BEST_PRACTICES.md                # Main guide (21KB)
├── ISSUE_DRIVEN_DEVELOPMENT.md                 # IDD methodology
├── PROGRESSIVE_DISCLOSURE_GUIDE.md             # Context optimization
├── MCP_TOKEN_AUDIT_CHECKLIST.md                # Token efficiency
├── mcp-second-opinion/                         # MCP server
│   └── src/server.py                           # 12 tools
├── scripts/
│   ├── terminal-label.sh                       # Terminal labeling
│   ├── session-lock.sh                         # Lock coordination
│   ├── session-register.sh                     # Session lifecycle
│   ├── session-heartbeat.sh                    # Heartbeat daemon
│   └── pytest-locked.sh                        # pytest wrapper
├── .claude/
│   ├── commands/
│   │   ├── coordination/                       # Session coordination
│   │   │   ├── pr-create.md                    # Coordinated PR creation
│   │   │   └── merge-main.md                   # Coordinated merges
│   │   ├── django/                             # Django workflow commands
│   │   ├── github/                             # GitHub issue management
│   │   ├── project-next.md                     # Next steps orchestrator
│   │   └── project-lite.md                     # Quick reference
│   ├── skills/best-practices.md                # On-demand best practices
│   └── hooks.json                              # Session/label/coordination hooks
├── .github/
│   └── ISSUE_TEMPLATE/                         # Structured issue templates
└── README.md                                    # Quick start guide
```

## On-Demand Documentation Loading

To preserve context, documentation is NOT auto-loaded. Use these commands when needed:

- `/load-best-practices` - Load full community wisdom
- `/load-mcp-docs` - Load MCP server documentation
- Or trigger the `best-practices` skill with relevant keywords

## Django Workflow Commands

**Note:** These commands are defined in this repository's `.claude/commands/django/` directory. To use them in other projects:

**Option 1 - Copy to your project:**
```bash
cp -r /home/cooneycw/Projects/claude-power-pack/.claude/commands/django ~/.claude/commands/
```

**Option 2 - Symlink from this repo (recommended):**
```bash
mkdir -p ~/.claude/commands
ln -s /home/cooneycw/Projects/claude-power-pack/.claude/commands/django ~/.claude/commands/django
```

Available commands:
- `/django:init` - Create new Django project with best practices
- `/django:worktree-setup` - Configure git worktrees for dev/staging/prod
- `/django:worktree-explain` - Learn about git worktrees

## GitHub Issue Management

Manage issues in this repository directly from Claude Code.

Commands:
- `/github:help` - Overview of all GitHub commands
- `/github:issue-list` - List and search issues
- `/github:issue-create` - Create new issues with guided prompts
- `/github:issue-view` - View issue details and comments
- `/github:issue-update` - Update existing issues
- `/github:issue-close` - Close issues with optional comment

## Terminal Labeling

Visual feedback for multi-session/multi-worktree workflows.

**Setup:**
```bash
mkdir -p ~/.claude/scripts
ln -sf /path/to/claude-power-pack/scripts/terminal-label.sh ~/.claude/scripts/
```

**Commands:**
- `terminal-label.sh issue PREFIX NUM [TITLE]` - Set issue-based label
- `terminal-label.sh project PREFIX` - Set project selection mode
- `terminal-label.sh await` - Show "Awaiting Input" (via Stop hook)
- `terminal-label.sh restore` - Restore saved label (via UserPromptSubmit hook)

See `ISSUE_DRIVEN_DEVELOPMENT.md` for integration with git worktrees.

## Project Commands

Commands for project orientation and issue management:

| Command | Purpose | Token Cost |
|---------|---------|------------|
| `/project-lite` | Quick project reference | ~500-800 |
| `/project-next` | Full issue analysis & prioritization | ~15-30K |

### /project-lite

Context-efficient quick reference that outputs:
- Repository info and conventions
- Worktree summary (if applicable)
- Key files presence check
- Available commands

**Use when:** Starting a session, context is high, or you know what to work on.

### /project-next

Full orchestrator for GitHub issue prioritization:
- Analyze open issues with hierarchy awareness (Wave/Phase patterns)
- Map worktrees to issues for context-aware recommendations
- Prioritize actions: Critical → In Progress → Ready → Quick Wins
- Set terminal labels for the selected work

**Use when:** Unsure what to work on, need issue analysis, or want cleanup suggestions.

## Session Coordination

Prevent conflicts between concurrent Claude Code sessions.

### Problem Solved
- Sessions competing for PR creation
- pytest runs killed by other sessions
- No visibility into active work
- Worktree cleanup conflicts

### Setup
```bash
# Symlink scripts
ln -sf ~/Projects/claude-power-pack/scripts/session-*.sh ~/.claude/scripts/
ln -sf ~/Projects/claude-power-pack/scripts/pytest-locked.sh ~/.claude/scripts/

# Create coordination directory
mkdir -p ~/.claude/coordination/{locks,sessions,heartbeat}
```

### Commands

| Script | Purpose |
|--------|---------|
| `session-lock.sh list` | Show active locks |
| `session-lock.sh acquire NAME` | Acquire a lock |
| `session-lock.sh release NAME` | Release a lock |
| `session-register.sh status` | Show active sessions |
| `pytest-locked.sh [args]` | Run pytest with coordination |

### Skill Commands

| Command | Purpose |
|---------|---------|
| `/coordination:pr-create` | Create PR with locking |
| `/coordination:merge-main BRANCH` | Merge to main with locking |

### Hook Integration

Hooks automatically:
- Register session at start
- Update heartbeat on each prompt
- Mark session paused on stop

See `ISSUE_DRIVEN_DEVELOPMENT.md` for detailed documentation.

## Version

Current version: 1.9.0
Previous: 1.8.0 (Project Commands)
