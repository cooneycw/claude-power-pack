# Claude Power Pack

## Project Overview

This repository contains four main components:
1. **Claude Code Best Practices** - Community wisdom from r/ClaudeCode
2. **MCP Second Opinion Server** - Gemini-powered code review
3. **MCP Playwright Server** - Browser automation for testing
4. **MCP Coordination Server** - Redis-backed distributed locking

## Quick References

- **Best Practices:** `CLAUDE_CODE_BEST_PRACTICES.md`
- **Issue-Driven Development:** `ISSUE_DRIVEN_DEVELOPMENT.md`
- **Progressive Disclosure:** `PROGRESSIVE_DISCLOSURE_GUIDE.md`
- **MCP Token Audit:** `MCP_TOKEN_AUDIT_CHECKLIST.md`
- **MCP Second Opinion:** `mcp-second-opinion/`
- **MCP Playwright:** `mcp-playwright-persistent/`
- **MCP Coordination:** `mcp-coordination/`

## Key Conventions

- Python 3.11+
- Use conda environments for MCP servers
- MCP Second Opinion: port 8080
- MCP Playwright: port 8081
- MCP Coordination: port 8082
- All documentation uses progressive disclosure principles

## Repository Structure

```
claude-power-pack/
├── CLAUDE_CODE_BEST_PRACTICES.md                # Main guide (21KB)
├── ISSUE_DRIVEN_DEVELOPMENT.md                 # IDD methodology
├── PROGRESSIVE_DISCLOSURE_GUIDE.md             # Context optimization
├── MCP_TOKEN_AUDIT_CHECKLIST.md                # Token efficiency
├── mcp-second-opinion/                         # MCP Second Opinion server
│   └── src/server.py                           # 12 tools
├── mcp-playwright-persistent/                  # MCP Playwright server
│   └── src/server.py                           # 20+ tools (browser automation)
├── mcp-coordination/                           # MCP Coordination server
│   └── src/server.py                           # 8 tools (Redis locking)
├── lib/secrets/                                # NEW: Secrets management
│   ├── base.py                                 # SecretValue, SecretsProvider
│   ├── credentials.py                          # DatabaseCredentials with masking
│   ├── masking.py                              # Output masking patterns
│   ├── permissions.py                          # Access control model
│   └── providers/                              # AWS, env providers
├── scripts/
│   ├── prompt-context.sh                       # Shell prompt context
│   ├── session-lock.sh                         # Lock coordination
│   ├── session-register.sh                     # Session lifecycle
│   ├── session-heartbeat.sh                    # Heartbeat daemon
│   ├── pytest-locked.sh                        # pytest wrapper
│   ├── worktree-remove.sh                      # Safe worktree removal
│   ├── conda-detect.sh                         # NEW: Conda env detection
│   ├── conda-activate.sh                       # NEW: Conda activation
│   ├── secrets-mask.sh                         # NEW: Output masking
│   ├── secrets-get.sh                          # NEW: Get credentials
│   └── secrets-validate.sh                     # NEW: Validate credentials
├── .claude/
│   ├── commands/
│   │   ├── coordination/                       # Session coordination
│   │   │   ├── pr-create.md                    # Coordinated PR creation
│   │   │   └── merge-main.md                   # Coordinated merges
│   │   ├── github/                             # GitHub issue management
│   │   ├── secrets/                            # NEW: Secrets commands
│   │   ├── env/                                # NEW: Environment commands
│   │   ├── project-next.md                     # Next steps orchestrator
│   │   └── project-lite.md                     # Quick reference
│   ├── skills/
│   │   ├── best-practices.md                   # On-demand best practices
│   │   └── secrets.md                          # NEW: Secrets skill
│   └── hooks.json                              # Session/conda hooks
├── .github/
│   └── ISSUE_TEMPLATE/                         # Structured issue templates
└── README.md                                    # Quick start guide
```

## On-Demand Documentation Loading

To preserve context, documentation is NOT auto-loaded. Use these commands when needed:

- `/load-best-practices` - Load full community wisdom
- `/load-mcp-docs` - Load MCP server documentation
- Or trigger the `best-practices` skill with relevant keywords

## GitHub Issue Management

Manage issues in this repository directly from Claude Code.

Commands:
- `/github:help` - Overview of all GitHub commands
- `/github:issue-list` - List and search issues
- `/github:issue-create` - Create new issues with guided prompts
- `/github:issue-view` - View issue details and comments
- `/github:issue-update` - Update existing issues
- `/github:issue-close` - Close issues with optional comment

## Worktree Context in Shell Prompt

Display current project and issue in your shell prompt for multi-worktree workflows.

**Setup (add to `~/.bashrc`):**
```bash
# Claude Code worktree context
ln -sf ~/Projects/claude-power-pack/scripts/prompt-context.sh ~/.claude/scripts/
export PS1='$(~/.claude/scripts/prompt-context.sh)\w $ '
```

**For Zsh (`~/.zshrc`):**
```zsh
precmd() { PS1="$(~/.claude/scripts/prompt-context.sh)%~ %% " }
```

**Result:**
```bash
# On issue branch (issue-42-auth)
[CPP #42] ~/Projects/claude-power-pack-issue-42 $

# On wave branch (wave-5c.1-feature or wave-5c-1-feature)
[CPP W5c.1] ~/Projects/claude-power-pack $

# On main branch
[CPP] ~/Projects/claude-power-pack $
```

**Customization:**
Create `.claude-prefix` in project root to set custom prefix:
```bash
echo "NHL" > .claude-prefix
```

See `ISSUE_DRIVEN_DEVELOPMENT.md` for integration with git worktrees.

## Safe Worktree Removal

Prevents the critical mistake of removing a worktree while working from it (which breaks the shell session).

**Setup:**
```bash
# Symlink to user scripts (recommended)
ln -sf ~/Projects/claude-power-pack/scripts/worktree-remove.sh ~/.claude/scripts/

# Or symlink to project scripts
ln -sf ~/Projects/claude-power-pack/scripts/worktree-remove.sh /path/to/project/scripts/
```

**Usage:**
```bash
# Basic removal (checks for uncommitted changes)
worktree-remove.sh /path/to/worktree

# Also delete the branch after removal
worktree-remove.sh /path/to/worktree --delete-branch

# Force remove even with uncommitted changes
worktree-remove.sh /path/to/worktree --force --delete-branch
```

**Safety Features:**
- Refuses to remove worktree if you're currently in it
- Checks for uncommitted changes (unless --force)
- Handles squash-merged branches (prompts for force-delete)
- Works with relative or absolute paths

**Why this matters:** If Claude Code's working directory is a worktree that gets removed, the shell session breaks completely and no bash commands can run.

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
- Recommend next issue to work on

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

## MCP Coordination Server

Redis-backed distributed locking for multi-session coordination.

### Features

- **Distributed Locks**: Prevent concurrent pytest runs, PR conflicts
- **Wave/Issue Hierarchy**: Lock at issue, wave, or wave.issue level
- **Auto-Detection**: Use "work" to lock based on current git branch
- **Session Tracking**: See all active Claude Code sessions
- **Auto-Expiry**: Locks and sessions expire automatically

### Prerequisites

```bash
# Install Redis
sudo apt install redis-server
sudo systemctl enable redis-server
redis-cli ping  # Should return PONG
```

### Setup

```bash
# Create conda environment
cd mcp-coordination
conda env create -f environment.yml
conda activate mcp-coordination

# Start server
./start-server.sh
```

### Add to Claude Code

```bash
claude mcp add coordination --transport sse --url http://127.0.0.1:8082/sse
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `acquire_lock(name, timeout)` | Acquire distributed lock |
| `release_lock(name)` | Release held lock |
| `check_lock(name)` | Check lock availability |
| `list_locks(pattern)` | List locks matching pattern |
| `register_session(metadata)` | Register session for tracking |
| `heartbeat()` | Update session heartbeat |
| `session_status()` | Show all sessions and states |
| `health_check()` | Check Redis connection |

### Lock Naming

```
# Auto-detect from branch
acquire_lock("work")          # issue-42-auth → issue:42
                              # wave-5c.1-feat → wave:5c.1

# Explicit locks
acquire_lock("issue:42")      # Issue-specific
acquire_lock("wave:5c")       # Wave-level
acquire_lock("pytest")        # Resource lock
```

### Usage Example

```
# Before running pytest
Use coordination MCP: acquire_lock("pytest", 600)
[run pytest]
Use coordination MCP: release_lock("pytest")
```

See `mcp-coordination/README.md` for detailed documentation.

## Secrets Management

Secure credential access with provider abstraction and output masking.

### Features

- **Provider abstraction**: AWS Secrets Manager + environment variables
- **Output masking**: Never exposes actual secret values
- **Permission model**: Read-only by default, writes require explicit permission
- **Bash wrappers**: Works in non-Python workflows

### Setup

```bash
# Symlink scripts
ln -sf ~/Projects/claude-power-pack/scripts/secrets-*.sh ~/.claude/scripts/
ln -sf ~/Projects/claude-power-pack/scripts/conda-*.sh ~/.claude/scripts/

# Add lib to PYTHONPATH (for Python usage)
export PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"
```

### Commands

| Command | Purpose |
|---------|---------|
| `/secrets:get [id]` | Get credentials (masked output) |
| `/secrets:validate` | Test credential configuration |
| `/env:detect` | Show detected conda environment |

### Python Usage

```python
from lib.secrets import get_credentials

creds = get_credentials()  # Auto-detects provider
print(creds)  # Password masked as ****
conn = await asyncpg.connect(**creds.dsn)  # dsn has real password
```

### Bash Usage

```bash
# Get credentials (masked)
~/.claude/scripts/secrets-get.sh

# Validate configuration
~/.claude/scripts/secrets-validate.sh --db

# Mask output
some_command | ~/.claude/scripts/secrets-mask.sh
```

## Conda Environment Detection

Automatic conda environment detection on session start.

### Detection Priority

1. `CONDA_ENV_NAME` environment variable
2. `.conda-env` file in project root
3. `environment.yml` name field
4. Directory name matching conda env

### Commands

```bash
# Show detection info
~/.claude/scripts/conda-detect.sh --info

# Get activation command
~/.claude/scripts/conda-detect.sh --activate

# Run command in detected env
~/.claude/scripts/conda-detect.sh --run pytest tests/
```

### Creating .conda-env

For projects without `environment.yml`:

```bash
echo "my-project-env" > .conda-env
```

## Version

Current version: 2.2.0
Previous: 2.1.0 (Shell prompt context)
