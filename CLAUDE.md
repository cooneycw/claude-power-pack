# Claude Power Pack

## Project Overview

This repository contains four core components and optional extras:
1. **Claude Code Best Practices** - Community wisdom from r/ClaudeCode
2. **Spec-Driven Development** - GitHub Spec Kit integration for structured workflows
3. **MCP Second Opinion Server** - Gemini-powered code review
4. **MCP Playwright Server** - Browser automation for testing
5. **Redis Coordination** (optional, in `extras/`) - Distributed locking for teams

## Quick References

- **Best Practices:** `docs/skills/` (fragmented) or `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md`
- **Issue-Driven Development:** `ISSUE_DRIVEN_DEVELOPMENT.md`
- **Spec-Driven Development:** `.specify/` (GitHub Spec Kit integration)
- **Progressive Disclosure:** `PROGRESSIVE_DISCLOSURE_GUIDE.md`
- **MCP Token Audit:** `MCP_TOKEN_AUDIT_CHECKLIST.md`
- **MCP Second Opinion:** `mcp-second-opinion/`
- **MCP Playwright:** `mcp-playwright-persistent/`
- **MCP Coordination (optional):** `extras/redis-coordination/`

## Key Conventions

- Python 3.11+
- Use uv for dependency management (pyproject.toml)
- MCP Second Opinion: port 8080
- MCP Playwright: port 8081
- MCP Coordination: port 8082
- All documentation uses progressive disclosure principles

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `CLAUDE_PROJECT` | Default project for `/project-next` when run from `~/Projects` | `claude-power-pack` |

**Setup (add to `~/.bashrc`):**
```bash
export CLAUDE_PROJECT="claude-power-pack"  # Default project
```

This allows running `/project-next` from `~/Projects` without being in a specific project directory.

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
├── extras/                                      # Optional components
│   └── redis-coordination/                     # Distributed locking (teams only)
│       ├── mcp-server/                         # MCP Coordination server (8 tools)
│       └── scripts/                            # Session coordination scripts
├── lib/creds/                                  # Secrets management
│   ├── __init__.py                             # Main exports + get_bundle_provider()
│   ├── __main__.py                             # python -m lib.creds entry
│   ├── base.py                                 # SecretValue, SecretBundle, BundleProvider
│   ├── cli.py                                  # CLI (get, set, list, run, ui, rotate)
│   ├── project.py                              # Project identity (git-based)
│   ├── config.py                               # SecretsConfig from .claude/secrets.yml
│   ├── audit.py                                # Audit logging (actions only, never values)
│   ├── run.py                                  # Secret injection for subprocess exec
│   ├── credentials.py                          # DatabaseCredentials with masking
│   ├── masking.py                              # Output masking patterns
│   ├── permissions.py                          # Access control model
│   ├── providers/                              # Secret providers
│   │   ├── env.py                              # Legacy env var provider
│   │   ├── dotenv.py                           # Global config .env provider
│   │   └── aws.py                              # AWS SM with bundle + IAM
│   └── ui/                                     # FastAPI web UI
│       └── app.py                              # Local-only CRUD with auth
├── lib/security/                               # Security scanning
│   ├── __init__.py                             # Main exports
│   ├── __main__.py                             # python -m lib.security entry
│   ├── cli.py                                  # CLI (scan, quick, deep, explain, gate)
│   ├── config.py                               # SecurityConfig, gate policies
│   ├── explain.py                              # Detailed finding explanations
│   ├── models.py                               # Finding, Severity, ScanResult
│   ├── orchestrator.py                         # Scan orchestration, suppression
│   ├── modules/                                # Scanner modules
│   │   ├── gitignore.py                        # .gitignore coverage check
│   │   ├── permissions.py                      # File permission audit
│   │   ├── secrets.py                          # Native secret detection
│   │   ├── env_files.py                        # .env tracking detection
│   │   ├── debug_flags.py                      # Debug flag detection
│   │   ├── gitleaks.py                         # External: gitleaks adapter
│   │   ├── pip_audit.py                        # External: pip-audit adapter
│   │   └── npm_audit.py                        # External: npm audit adapter
│   └── output/                                 # Output formatters
│       ├── novice.py                           # Human-friendly output
│       └── json_output.py                      # Machine-readable JSON
├── lib/spec_bridge/                            # Spec-to-Issue sync
│   ├── __init__.py                             # Module exports
│   ├── parser.py                               # Parse spec/tasks files
│   ├── issue_sync.py                           # GitHub issue creation
│   ├── status.py                               # Alignment checking
│   └── cli.py                                  # Command-line interface
├── scripts/
│   ├── prompt-context.sh                       # Shell prompt context
│   ├── worktree-remove.sh                      # Safe worktree removal
│   ├── secrets-mask.sh                         # Output masking
│   ├── hook-mask-output.sh                     # PostToolUse: mask secrets
│   └── hook-validate-command.sh                # PreToolUse: block dangerous commands
├── .claude/
│   ├── commands/
│   │   ├── flow/                               # Flow workflow (stateless, git-native)
│   │   │   ├── start.md                        # Create worktree for issue
│   │   │   ├── status.md                       # Show active worktrees
│   │   │   ├── finish.md                       # Commit, push, create PR
│   │   │   ├── merge.md                        # Merge PR, clean up
│   │   │   ├── deploy.md                       # Run make deploy
│   │   │   ├── cleanup.md                      # Prune stale worktrees and branches
│   │   │   ├── auto.md                         # Full lifecycle automation
│   │   │   ├── doctor.md                       # Diagnose workflow environment
│   │   │   └── help.md                         # Flow command overview
│   │   ├── cpp/                                # CPP initialization wizard
│   │   │   ├── init.md                         # Interactive setup wizard
│   │   │   ├── status.md                       # Check installation state
│   │   │   └── help.md                         # Command overview
│   │   ├── github/                             # GitHub issue management
│   │   ├── spec/                               # Spec-Driven Development
│   │   │   ├── help.md                         # SDD command overview
│   │   │   ├── init.md                         # Initialize .specify/
│   │   │   ├── create.md                       # Create feature spec
│   │   │   ├── sync.md                         # Sync tasks to issues
│   │   │   └── status.md                       # Show spec status
│   │   ├── security/                            # Security scanning commands
│   │   │   ├── scan.md                         # Full security scan
│   │   │   ├── quick.md                        # Quick (native-only) scan
│   │   │   ├── deep.md                         # Deep scan (+ git history)
│   │   │   ├── explain.md                      # Explain a finding
│   │   │   └── help.md                         # Security command overview
│   │   ├── secrets/                            # Secrets management commands
│   │   │   ├── get.md                          # Get credentials (masked)
│   │   │   ├── set.md                          # Set a secret value
│   │   │   ├── list.md                         # List secret keys
│   │   │   ├── run.md                          # Run command with secrets
│   │   │   ├── validate.md                     # Validate configuration
│   │   │   ├── ui.md                           # Launch web UI
│   │   │   ├── rotate.md                       # Rotate a secret
│   │   │   └── help.md                         # Secrets command overview
│   │   ├── env/                                # Environment commands
│   │   ├── project-next.md                     # Next steps orchestrator
│   │   ├── project-lite.md                     # Quick reference
│   │   └── happy-check.md                      # Happy CLI version check (optional)
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
│   └── hooks.json                              # Session hooks
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

## Quick Start: /cpp:init

The easiest way to set up Claude Power Pack is with the interactive wizard:

```bash
/cpp:init
```

This guides you through a tiered installation:

| Tier | What's Installed |
|------|------------------|
| **Minimal** | Commands + Skills symlinks |
| **Standard** | + Scripts, hooks, shell prompt |
| **Full** | + MCP servers (uv, API keys) |

Run `/cpp:status` to check current installation, `/cpp:help` for all commands.

## Manual Setup (Alternative)

If you prefer manual setup, commands and skills must be installed in your **project's** `.claude` directory (where Claude Code starts), NOT the user home `~/.claude` directory.

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

### Python CLI (lib/spec_bridge)

For programmatic or CLI usage:

```bash
# Add lib to PYTHONPATH
export PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"

# Show status of all specs
python -m lib.spec_bridge status

# Show specific feature status
python -m lib.spec_bridge status user-auth

# Sync feature to issues (dry run)
python -m lib.spec_bridge sync user-auth --dry-run

# Sync feature to issues
python -m lib.spec_bridge sync user-auth

# Sync all features
python -m lib.spec_bridge sync --all
```

Python API:
```python
from lib.spec_bridge import parse_tasks, sync_feature, get_all_status

# Parse tasks from spec
waves = parse_tasks(".specify/specs/user-auth/tasks.md")
for wave in waves:
    print(f"{wave.name}: {len(wave.tasks)} tasks")

# Sync to GitHub issues
result = sync_feature("user-auth", dry_run=True)
print(f"Would create {len(result.issues_created)} issues")

# Get project status
status = get_all_status()
print(f"{status.total_features} features, {status.total_pending} pending sync")
```

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

## CPP Commands

Commands for managing Claude Power Pack installation:

| Command | Purpose |
|---------|---------|
| `/cpp:init` | Interactive setup wizard (tiered installation) |
| `/cpp:status` | Check current installation state |
| `/cpp:help` | Overview of all CPP commands |

### Installation Tiers

| Tier | Name | What's Included |
|------|------|-----------------|
| 1 | Minimal | Commands + Skills symlinks |
| 2 | Standard | + Scripts, hooks, shell prompt |
| 3 | Full | + MCP servers (uv, API keys, systemd), optional extras |

The wizard detects existing configuration and skips already-installed components (idempotent).

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

## Optional Installs

Optional packages offered during `/cpp:init` (Tier 2):

| Package | Purpose | Install Command |
|---------|---------|-----------------|
| happy-cli | AI coding assistant | `npm install -g happy-coder` |

### happy-cli

[Happy CLI](https://github.com/slopus/happy-cli) is an AI coding assistant that complements Claude Code. If installed via the wizard, CPP provides `/happy-check` to verify your version is current.

### /happy-check

Checks if the installed happy-cli is on the latest version:
- Compares installed version against GitHub releases
- Reports update availability
- Checks onboarding status

**Use when:** You have happy-cli installed and want to verify you're on the latest version.

## Session Coordination (Optional)

> **Moved to `extras/redis-coordination/` in v4.0.0.** Most users don't need this — the default `/flow` workflow is stateless and conflict-free for solo development.

For teams running multiple concurrent Claude Code sessions, coordination scripts and the Redis MCP server prevent conflicts (duplicate PRs, pytest interference, etc.).

### Setup (if needed)

```bash
# Symlink scripts from extras
ln -sf ~/Projects/claude-power-pack/extras/redis-coordination/scripts/*.sh ~/.claude/scripts/

# Create coordination directory
mkdir -p ~/.claude/coordination/{locks,sessions,heartbeat}
```

### Coordination Tiers

| Tier | Mode | Description |
|------|------|-------------|
| **Local** (default) | `coordination: local` | Stateless. Context from git. No locking. |
| **Git** (optional) | `coordination: git` | State in `.claude/state.json`, synced via git. |
| **Redis** (teams) | `coordination: redis` | MCP server with distributed locks. |

See `extras/redis-coordination/README.md` for full documentation.

## Security Hooks

Automatic protection for Claude Code sessions.

### Secret Masking (PostToolUse)

All Bash and Read tool output is automatically masked:
- Connection strings (postgresql://, mysql://, etc.)
- API keys (OpenAI, Anthropic, GitHub, AWS, etc.)
- Environment variables (DB_PASSWORD, API_KEY, etc.)

**Setup:**
```bash
ln -sf ~/Projects/claude-power-pack/scripts/hook-mask-output.sh ~/.claude/scripts/
```

### Dangerous Command Blocking (PreToolUse)

Warns before executing destructive commands:
- `git push --force` to main/master
- `git reset --hard`
- `rm -rf /` or system directories
- `DROP TABLE`, `DELETE FROM` without WHERE
- `TRUNCATE TABLE`

**Setup:**
```bash
ln -sf ~/Projects/claude-power-pack/scripts/hook-validate-command.sh ~/.claude/scripts/
```

### Hook Configuration

Hooks are configured in `.claude/hooks.json`:

| Hook | Trigger | Purpose |
|------|---------|---------|
| PreToolUse (Bash) | Before command | Block dangerous operations |
| PostToolUse (Bash/Read) | After tool | Mask secrets in output |

## Security Scanning

Novice-friendly security scanning with `/flow` integration.

### Commands

| Command | Purpose |
|---------|---------|
| `/security:scan` | Full scan: native checks + available external tools |
| `/security:quick` | Fast scan: native checks only (zero deps) |
| `/security:deep` | Deep scan: includes git history analysis |
| `/security:explain <ID>` | Detailed explanation of a finding type |
| `/security:help` | Overview of security commands |

### CLI Usage

```bash
# Add lib to PYTHONPATH
export PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"

# Run full scan
python3 -m lib.security scan

# Quick scan (native only)
python3 -m lib.security quick

# Deep scan (includes git history)
python3 -m lib.security deep

# Explain a finding
python3 -m lib.security explain HARDCODED_PASSWORD

# Check flow gate
python3 -m lib.security gate flow_finish
```

### /flow Integration

- `/flow:finish` runs security quick scan as a quality gate
- `/flow:deploy` runs security quick scan before deploying
- CRITICAL findings block the gate; HIGH findings produce warnings
- Configure gating behavior in `.claude/security.yml`

### Configuration

Create `.claude/security.yml` to customize gate behavior and suppress known findings:

```yaml
gates:
  flow_finish:
    block_on: [critical]
    warn_on: [high]
  flow_deploy:
    block_on: [critical, high]
    warn_on: [medium]
suppressions:
  - id: HARDCODED_SECRET
    path: tests/fixtures/.*
    reason: "Test fixtures with fake credentials"
```

## MCP Coordination Server (Optional)

> **Moved to `extras/redis-coordination/mcp-server/` in v4.0.0.** Only needed for teams.

Redis-backed distributed locking for multi-session coordination. See `extras/redis-coordination/README.md` for setup and usage.

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
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Playwright browsers
cd mcp-playwright-persistent
uv run playwright install chromium

# Start server (uv handles dependencies automatically)
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

Tiered secrets management scaling from `.env` files to AWS Secrets Manager, with a FastAPI web UI.

### Tiered Architecture

| Tier | Provider | Storage | Use Case |
|------|----------|---------|----------|
| **0** | `dotenv-global` | `~/.config/claude-power-pack/secrets/{project_id}/.env` | Local dev (default) |
| **1** | `env-file` | Environment variables / `.env` in repo | Legacy compat |
| **2** | `aws-secrets-manager` | AWS Secrets Manager | Production |

### Features

- **Project identity**: Stable ID from git repo root, shared across worktrees
- **Bundle API**: CRUD operations for project secrets (get, set, delete, list)
- **Secret injection**: `creds run -- cmd` injects secrets as env vars (never in CLI args)
- **FastAPI UI**: Local-only web interface with bearer token auth
- **Audit logging**: Actions logged to `~/.config/claude-power-pack/audit.log` (never values)
- **IAM isolation**: Per-project AWS roles with scoped policies
- **Output masking**: Never exposes actual secret values
- **Permission model**: Read-only by default, writes require explicit permission

### Setup

```bash
# Add lib to PYTHONPATH
export PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"

# For masking pipe filter (bash-only)
ln -sf ~/Projects/claude-power-pack/scripts/secrets-mask.sh ~/.claude/scripts/
```

### CLI Usage

```bash
# Set a secret
python -m lib.creds set DB_PASSWORD my-secret-value

# List all secrets (masked)
python -m lib.creds list

# Run command with secrets injected
python -m lib.creds run -- make deploy

# Launch web UI
python -m lib.creds ui

# Rotate a secret
python -m lib.creds rotate DB_PASSWORD

# Get database credentials (legacy)
python -m lib.creds get

# Validate all providers
python -m lib.creds validate
```

### Commands

| Command | Purpose |
|---------|---------|
| `/secrets:get [id]` | Get credentials (masked output) |
| `/secrets:set KEY VALUE` | Set or update a secret |
| `/secrets:list` | List all secret keys (masked) |
| `/secrets:run -- CMD` | Run command with secrets injected |
| `/secrets:validate` | Test credential configuration |
| `/secrets:ui` | Launch web UI for management |
| `/secrets:rotate KEY` | Rotate a secret value |
| `/secrets:help` | Overview of all commands |

### Python Usage

```python
# Bundle API (recommended)
from lib.creds import get_bundle_provider
from lib.creds.project import get_project_id

provider = get_bundle_provider()
bundle = provider.get_bundle(get_project_id())
print(bundle)  # Keys visible, values masked

# Legacy credentials API
from lib.creds import get_credentials
creds = get_credentials()  # Auto-detects provider
conn = await asyncpg.connect(**creds.dsn)  # dsn has real password
```

### Configuration

Create `.claude/secrets.yml` for project-level settings:

```yaml
default_provider: auto  # auto, dotenv, aws
aws:
  region: us-east-1
  role_arn: ""  # Optional IAM role for isolation
ui:
  host: 127.0.0.1
  port: 8090
rotation:
  warn_days: 90
```

### Masking Pipe Filter

```bash
# Mask secrets in any command output
some_command | ~/.claude/scripts/secrets-mask.sh
```

## Python Environment (uv)

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management.

### Quick Start

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run any MCP server (dependencies installed automatically)
cd mcp-second-opinion
./start-server.sh

# Or run directly with uv
uv run python src/server.py
```

### Project Structure

Each Python component has its own `pyproject.toml`:
- `mcp-second-opinion/pyproject.toml`
- `mcp-playwright-persistent/pyproject.toml`
- `extras/redis-coordination/mcp-server/pyproject.toml`
- `lib/creds/pyproject.toml`
- `lib/security/pyproject.toml`
- `lib/spec_bridge/pyproject.toml`

## Version

Current version: 4.0.0 (Simplified Workflow)
Previous: 3.0.0 (uv migration)
