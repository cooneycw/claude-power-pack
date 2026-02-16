---
description: Overview of Claude Power Pack (CPP) commands
---

# Claude Power Pack Commands

CPP provides commands for setting up and managing Claude Code enhancements.

## Available Commands

| Command | Description |
|---------|-------------|
| `/cpp:init` | Interactive setup wizard - install CPP components |
| `/cpp:status` | Check current installation state |
| `/cpp:help` | This help overview |

## Installation Tiers

CPP uses a tiered installation model:

| Tier | Name | What's Included |
|------|------|-----------------|
| 1 | **Minimal** | Commands + Skills symlinks |
| 2 | **Standard** | + Scripts, hooks, shell prompt |
| 3 | **Full** | + MCP servers (uv, API keys) |

## Quick Start

```bash
# Check what's installed
/cpp:status

# Run the setup wizard
/cpp:init
```

## Components

### Tier 1 - Minimal
- **Commands**: `/project-next`, `/flow:*`, `/spec:*`, `/github:*`
- **Skills**: Best practices loaders, secrets management

### Tier 2 - Standard
- **Scripts**: Secret masking, worktree cleanup, shell prompt context
- **Hooks**: Security (command validation, output masking)
- **Shell prompt**: Worktree context display (`[CPP #42]`)

### Tier 3 - Full
- **MCP Second Opinion** (port 8080): Gemini/OpenAI code review
- **MCP Playwright** (port 8081): Persistent browser automation
- **Systemd services**: Auto-start on boot (optional)

### Optional Add-on
- **Redis Coordination** (`extras/`): Distributed locking for team/multi-session use

## Related Documentation

- `CLAUDE.md` - Full project documentation
- `ISSUE_DRIVEN_DEVELOPMENT.md` - IDD workflow guide
- `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` - Community best practices
