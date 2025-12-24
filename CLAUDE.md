# Claude Power Pack

## Project Overview

This repository contains five main components:
1. **Claude Code Best Practices** - Community wisdom from r/ClaudeCode
2. **Spec-Driven Development** - GitHub Spec Kit integration for structured workflows
3. **MCP Second Opinion Server** - Gemini-powered code review
4. **MCP Playwright Server** - Browser automation for testing
5. **MCP Coordination Server** - Redis-backed distributed locking

## Quick References

- **Best Practices:** `docs/skills/` (fragmented) or `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md`
- **Issue-Driven Development:** `ISSUE_DRIVEN_DEVELOPMENT.md`
- **Spec-Driven Development:** `.specify/` (GitHub Spec Kit integration)
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
├── docs/
│   ├── skills/                                 # Topic-focused best practices (~3K each)
│   │   ├── context-efficiency.md               # Token optimization
│   │   ├── session-management.md               # Session & plan mode
│   │   ├── mcp-optimization.md                 # MCP best practices
│   │   ├── skills-patterns.md                  # Skill design
│   │   ├── hooks-automation.md                 # Hook system
│   │   ├── spec-driven-dev.md                  # SDD workflow
│   │   ├── idd-workflow.md                     # Issue-driven dev
│   │   ├── claude-md-config.md                 # CLAUDE.md tips
│   │   └── code-quality.md                     # Quality patterns
│   └── reference/
│       └── CLAUDE_CODE_BEST_PRACTICES_FULL.md  # Complete guide (25K tokens)
├── ISSUE_DRIVEN_DEVELOPMENT.md                 # IDD methodology
├── PROGRESSIVE_DISCLOSURE_GUIDE.md             # Context optimization
├── MCP_TOKEN_AUDIT_CHECKLIST.md                # Token efficiency
├── .specify/                                    # Spec-Driven Development
│   ├── memory/
│   │   └── constitution.md                     # Project principles template
│   ├── specs/                                  # Feature specifications
│   └── templates/                              # Spec, plan, tasks templates
├── mcp-second-opinion/                         # MCP Second Opinion server
│   └── src/server.py                           # 12 tools
├── mcp-playwright-persistent/                  # MCP Playwright server
│   ├── src/server.py                           # 29 tools (browser automation)
│   ├── deploy/                                 # systemd, docker configs
│   └── README.md                               # Full documentation
├── mcp-coordination/                           # MCP Coordination server
│   └── src/server.py                           # 8 tools (Redis locking)
├── lib/secrets/                                # Secrets management
│   ├── __init__.py                             # Main exports
│   ├── __main__.py                             # python -m lib.secrets entry
│   ├── base.py                                 # SecretValue, SecretsProvider
│   ├── cli.py                                  # CLI (get, validate commands)
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
│   ├── conda-detect.sh                         # Conda env detection
│   ├── conda-activate.sh                       # Conda activation
│   └── secrets-mask.sh                         # Output masking
├── .claude/
│   ├── commands/
│   │   ├── coordination/                       # Session coordination
│   │   │   ├── pr-create.md                    # Coordinated PR creation
│   │   │   └── merge-main.md                   # Coordinated merges
│   │   ├── github/                             # GitHub issue management
│   │   ├── spec/                               # Spec-Driven Development
│   │   │   ├── help.md                         # SDD command overview
│   │   │   ├── init.md                         # Initialize .specify/
│   │   │   ├── create.md                       # Create feature spec
│   │   │   ├── sync.md                         # Sync tasks to issues
│   │   │   └── status.md                       # Show spec status
│   │   ├── secrets/                            # Secrets commands
│   │   ├── env/                                # Environment commands
│   │   ├── project-next.md                     # Next steps orchestrator
│   │   └── project-lite.md                     # Quick reference
│   ├── skills/                                 # Skill loaders (lightweight)
│   │   ├── best-practices.md                   # Dispatcher to topic skills
│   │   ├── context-efficiency.md               # → docs/skills/
│   │   ├── session-management.md               # → docs/skills/
│   │   ├── mcp-optimization.md                 # → docs/skills/
│   │   ├── skills-patterns.md                  # → docs/skills/
│   │   ├── hooks-automation.md                 # → docs/skills/
│   │   ├── spec-driven-dev.md                  # → docs/skills/
│   │   ├── idd-workflow.md                     # → docs/skills/
│   │   ├── claude-md-config.md                 # → docs/skills/
│   │   ├── code-quality.md                     # → docs/skills/
│   │   └── secrets.md                          # Secrets skill
│   └── hooks.json                              # Session/conda hooks
├── .github/
│   └── ISSUE_TEMPLATE/                         # Structured issue templates
└── README.md                                    # Quick start guide
```

## On-Demand Documentation Loading

To preserve context, documentation is NOT auto-loaded. Use topic-specific skills for 88-92% token savings:

**Topic Skills (load only what you need):**
| Topic | Trigger Keywords |
|-------|------------------|
| Context Efficiency | "context", "tokens", "optimization" |
| Session Management | "session", "reset", "plan mode" |
| MCP Optimization | "MCP", "token consumption" |
| Skills Patterns | "skill activation", "skill design" |
| Hooks & Automation | "hooks", "automation" |
| Spec-Driven Dev | "spec driven", "specification" |
| Issue-Driven Dev | "worktree", "IDD" |
| CLAUDE.md Config | "CLAUDE.md", "configuration" |
| Code Quality | "code review", "quality" |

**Commands:**
- `/load-best-practices` - Load full guide (25K tokens)
- `/load-mcp-docs` - Load MCP server documentation

## Using Commands/Skills in Other Projects

Commands and skills must be installed in your **project's** `.claude` directory (where Claude Code starts), NOT the user home `~/.claude` directory.

**Option 1 - Symlink to project (recommended):**
```bash
# In your project directory
mkdir -p .claude
ln -s /path/to/claude-power-pack/.claude/commands .claude/commands
ln -s /path/to/claude-power-pack/.claude/skills .claude/skills
```

**Option 2 - Symlink to parent directory (covers multiple projects):**
```bash
# In ~/Projects/.claude to cover all projects under ~/Projects
mkdir -p ~/Projects/.claude
ln -s /path/to/claude-power-pack/.claude/commands ~/Projects/.claude/commands
ln -s /path/to/claude-power-pack/.claude/skills ~/Projects/.claude/skills
```

**Note:** User scripts (like `prompt-context.sh`, `session-*.sh`) go in `~/.claude/scripts/` because they're shell utilities, not Claude Code commands.

## GitHub Issue Management

Manage issues in this repository directly from Claude Code.

Commands:
- `/github:help` - Overview of all GitHub commands
- `/github:issue-list` - List and search issues
- `/github:issue-create` - Create new issues with guided prompts
- `/github:issue-view` - View issue details and comments
- `/github:issue-update` - Update existing issues
- `/github:issue-close` - Close issues with optional comment

## Spec-Driven Development

Structured specification workflow based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).

### Workflow

```
Constitution (principles) → Spec (what) → Plan (how) → Tasks → Issues → Code
```

### Commands

| Command | Description |
|---------|-------------|
| `/spec:help` | Overview of spec commands |
| `/spec:init` | Initialize `.specify/` structure |
| `/spec:create NAME` | Create new feature specification |
| `/spec:sync [NAME]` | Sync tasks.md to GitHub issues |
| `/spec:status` | Show spec/issue alignment |

### Quick Start

```bash
# Initialize (once per project)
/spec:init
# Edit .specify/memory/constitution.md with your principles

# Create feature spec
/spec:create user-authentication
# Edit spec.md, plan.md, tasks.md in .specify/specs/user-authentication/

# Sync to GitHub issues
/spec:sync user-authentication
```

### Directory Structure

```
.specify/
├── memory/
│   └── constitution.md    # Project principles
├── specs/
│   └── {feature}/
│       ├── spec.md        # Requirements & user stories
│       ├── plan.md        # Technical approach
│       └── tasks.md       # Actionable items → Issues
└── templates/             # Reusable templates
```

### Integration with IDD

Spec commands integrate with Issue-Driven Development:
- Each wave in tasks.md becomes a GitHub issue
- Issues link back to spec files
- `/project-next` shows spec status alongside issues

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

## MCP Playwright Persistent

Persistent browser automation with session management for testing and web interaction.

### Features

- **Persistent Sessions**: Browser sessions survive across tool calls
- **Multi-Tab Support**: Open, switch, and manage multiple tabs
- **Full Automation**: Click, type, fill, select, hover, screenshot
- **Headless/Headed**: Run with or without visible browser
- **PDF Generation**: Export pages to PDF (headless only)

### Setup

```bash
# Create conda environment
cd mcp-playwright-persistent
conda env create -f environment.yml
conda activate mcp-playwright

# Install Playwright browsers
playwright install chromium

# Start server
./start-server.sh
```

### Add to Claude Code

```bash
claude mcp add playwright-persistent --transport sse --url http://127.0.0.1:8081/sse
```

### MCP Tools (29 total)

| Category | Tools |
|----------|-------|
| **Session** | `create_session`, `close_session`, `list_sessions`, `get_session_info`, `cleanup_idle_sessions` |
| **Navigation** | `browser_navigate`, `browser_click`, `browser_type`, `browser_fill`, `browser_select_option`, `browser_hover` |
| **Tabs** | `browser_new_tab`, `browser_switch_tab`, `browser_close_tab`, `browser_go_back`, `browser_go_forward`, `browser_reload` |
| **Capture** | `browser_screenshot`, `browser_snapshot`, `browser_pdf`, `browser_get_content`, `browser_get_text` |
| **Evaluation** | `browser_evaluate`, `browser_wait_for`, `browser_wait_for_navigation`, `browser_console_messages` |
| **Query** | `browser_get_attribute`, `browser_query_selector_all` |
| **Health** | `health_check` |

### Usage Example

```python
# Create a session
session = create_session(headless=True)

# Navigate and interact
browser_navigate(session["session_id"], "https://example.com")
browser_click(session["session_id"], "button#submit")

# Take screenshot
screenshot = browser_screenshot(session["session_id"], full_page=True)

# Close when done
close_session(session["session_id"])
```

See `mcp-playwright-persistent/README.md` for detailed documentation.

## Secrets Management

Secure credential access with provider abstraction and output masking.

### Features

- **Provider abstraction**: AWS Secrets Manager + environment variables
- **Output masking**: Never exposes actual secret values
- **Permission model**: Read-only by default, writes require explicit permission
- **Cross-platform CLI**: Python CLI works on Windows/Mac/Linux

### Setup

```bash
# Add lib to PYTHONPATH
export PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"

# For masking pipe filter (bash-only)
ln -sf ~/Projects/claude-power-pack/scripts/secrets-mask.sh ~/.claude/scripts/
```

### CLI Usage

```bash
# Get database credentials (auto-detect provider)
python -m lib.secrets get

# Get specific secret from AWS
python -m lib.secrets get --provider aws prod/database

# Get credentials as JSON (masked)
python -m lib.secrets get --json

# Validate all providers
python -m lib.secrets validate

# Validate specific provider
python -m lib.secrets validate --env
python -m lib.secrets validate --aws
python -m lib.secrets validate --db
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

### Masking Pipe Filter

```bash
# Mask secrets in any command output
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

Current version: 2.5.0
Previous: 2.4.0 (Fragmented best practices)
