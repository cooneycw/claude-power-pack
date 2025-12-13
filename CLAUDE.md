# Claude Power Pack

## Project Overview

This repository contains two main components:
1. **Claude Code Best Practices** - Community wisdom from r/ClaudeCode
2. **MCP Second Opinion Server** - Gemini-powered code review

## Quick References

- **Best Practices:** `CLAUDE_CODE_BEST_PRACTICES_COMPREHENSIVE.md`
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
├── CLAUDE_CODE_BEST_PRACTICES_COMPREHENSIVE.md  # Main guide (21KB)
├── CLAUDE_CODE_BEST_PRACTICES.md               # Quick reference (9.5KB)
├── PROGRESSIVE_DISCLOSURE_GUIDE.md             # Context optimization
├── MCP_TOKEN_AUDIT_CHECKLIST.md                # Token efficiency
├── mcp-second-opinion/                         # MCP server
│   └── src/server.py                           # 12 tools
├── .claude/
│   ├── commands/
│   │   ├── django/                             # Django workflow commands
│   │   └── github/                             # GitHub issue management
│   ├── skills/best-practices.md                # On-demand best practices
│   └── hooks.json                              # SessionStart update check
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

**New in v1.6.0:** Manage issues in this repository directly from Claude Code.

Commands:
- `/github:help` - Overview of all GitHub commands
- `/github:issue-list` - List and search issues
- `/github:issue-create` - Create new issues with guided prompts
- `/github:issue-view` - View issue details and comments
- `/github:issue-update` - Update existing issues
- `/github:issue-close` - Close issues with optional comment

## Version

Current version: 1.6.0
Previous: 1.5.0 (Multi-Model Second Opinion with Codex)
