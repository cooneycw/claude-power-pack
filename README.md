# Claude Code Power Pack 🚀

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP 1.2.0+](https://img.shields.io/badge/MCP-1.2.0+-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive repository combining:
1. **Claude Code Best Practices** - Curated wisdom from the r/ClaudeCode community
2. **MCP Second Opinion Server** - AI-powered code review using Google Gemini 3 Pro

## 🎯 Quick Navigation

- [Quick Start: /cpp:init](#-quick-start-cppinit) - **START HERE** - Interactive setup wizard
- [Claude Best Practices](#claude-best-practices) - Community insights & tips
- [Token-Efficient Tool Organization](#-token-efficient-tool-organization) - Progressive disclosure
- [Shell Prompt Context](#-shell-prompt-context) - Visual session management
- [Issue-Driven Development](#-issue-driven-development) - Micro-issue methodology
- [Flow Workflow](#-flow-workflow) - `/flow:start` → work → `/flow:finish` → `/flow:merge`
- [Spec-Driven Development](#-spec-driven-development) - Specification workflow
- [Sequential Thinking](#sequential-thinking-optional) - Structured step-by-step reasoning (optional)
- [Session Coordination](#-session-coordination) - Multi-session conflict prevention (optional)
- [Project Commands](#-project-commands) - `/project-lite` & `/project-next`
- [GitHub Issue Management](#-github-issue-management) - Full CRUD for issues
- [Secrets Management](#-secrets-management) - Secure credential access
- [Python Environment (uv)](#-python-environment-uv) - Dependency management
- [Security Hooks](#-security-hooks) - Secret masking & command validation
- [Security Scanning](#-security-scanning) - Vulnerability detection with `/flow` integration
- [CI/CD & Verification](#-cicd--verification-tier-4) - Framework-aware build & deploy
- [QA Testing](#-qa-testing) - Config-driven web testing with Playwright
- [PowerPoint & Diagrams](#-powerpoint--diagrams) - Nano-Banana MCP diagrams + PPTX
- [Evaluate Commands](#-evaluate-commands) - Multi-model evaluation flow
- [MCP Servers](#mcp-servers)
  - [MCP Second Opinion](#mcp-second-opinion-server) - Multi-model code review (port 8080)
  - [MCP Playwright Persistent](#mcp-playwright-persistent-server) - Browser automation (port 8081)
  - [MCP Coordination](#mcp-coordination-server-optional) - Redis-backed locking (optional, in `extras/`)
- [Installation](#installation) - Get started quickly
- [Disclosures & Legal](#-disclosures--legal) - Attribution & API terms

---

## 🚀 Quick Start: /cpp:init

The easiest way to set up Claude Power Pack is with the interactive wizard:

```bash
/cpp:init
```

This guides you through a tiered installation:

| Tier | Name | What's Installed |
|------|------|------------------|
| 1 | **Minimal** | Commands + Skills symlinks |
| 2 | **Standard** | + Scripts, hooks, shell prompt |
| 3 | **Full** | + MCP servers (uv, API keys, systemd), optional extras |
| 4 | **CI/CD** | + Framework detection, Makefile generation, health/smoke, pipelines, containers |

### CPP Commands

| Command | Purpose |
|---------|---------|
| `/cpp:init` | Interactive setup wizard (tiered installation) |
| `/cpp:status` | Check current installation state |
| `/cpp:help` | Overview of all CPP commands |

The wizard detects existing configuration and skips already-installed components (idempotent).

### Manual Setup (Alternative)

If you prefer manual setup, commands and skills must be installed in your **project's** `.claude` directory:

```bash
# In your project directory
mkdir -p .claude
ln -s /path/to/claude-power-pack/.claude/commands .claude/commands
ln -s /path/to/claude-power-pack/.claude/skills .claude/skills
```

Or in a parent directory to cover multiple projects:

```bash
# In ~/Projects/.claude to cover all projects under ~/Projects
mkdir -p ~/Projects/.claude
ln -s /path/to/claude-power-pack/.claude/commands ~/Projects/.claude/commands
ln -s /path/to/claude-power-pack/.claude/skills ~/Projects/.claude/skills
```

---

# Claude Best Practices

A comprehensive collection of Claude Code best practices compiled from the r/ClaudeCode community, based on 100+ top posts and thousands of upvotes.

## 📚 Best Practices Documents

### Main Guides

**[CLAUDE_CODE_BEST_PRACTICES.md](CLAUDE_CODE_BEST_PRACTICES.md)** ⭐ **START HERE**
- Complete guide with insights from 100+ top posts
- Based on posts with 600+ upvotes
- Covers: Skills, Hooks, MCP, Session Management, Plan Mode, and more
- ~21KB of curated community wisdom

## 🎯 Top 5 Quick Wins

1. **Use Plan Mode + "Please let me know if you have any questions before making the plan!"**
   - 20-30% better results
   - Forces clarification upfront

2. **Reset Sessions Frequently**
   - After each feature
   - At 60% context usage
   - When quality drops

3. **Optimize CLAUDE.md**
   - Can improve performance 5-10%
   - Include project-specific context
   - Update regularly

4. **Skills Need Good Activation Patterns**
   - Default: 20% activation
   - Possible: 84% activation
   - Key: Detailed, context-rich, specific triggers

5. **Choose 1-3 Quality MCPs**
   - More isn't better
   - Token consumption is real
   - Consider converting to Skills

## 🎯 Token-Efficient Tool Organization

**New in v1.1.0:** This repository now emphasizes **progressive disclosure** for tool context - a principle endorsed by Anthropic that dramatically improves agent efficiency.

### The Problem

- Claude's context window is finite (200K for Sonnet 4.5)
- Each MCP tool definition consumes 500-2000 tokens
- A typical multi-server setup can consume 50-100K tokens BEFORE any work
- This leaves less room for actual code, conversation, and task context

### The Solution: Gradual Tool Exposure

1. **Load metadata first** (~100 tokens per tool)
2. **Expand full instructions only when relevant** (<5K tokens)
3. **Load executable assets only when executing**

### Anthropic's Data

| Scenario | Token Consumption | Savings |
|----------|-------------------|---------|
| Traditional loading (100 tools) | ~77K tokens | - |
| With Tool Search Tool | ~8.7K tokens | **85%** |

**Tool Selection Accuracy:** 49% → 74% (Opus 4), 79.5% → 88.1% (Opus 4.5)

### Quick Wins

1. Use `/context` to audit your current token usage
2. Disable MCP servers you don't need for the current session
3. Consolidate similar tools (4 search tools → 1 with parameter)
4. Convert procedural knowledge from MCP to Skills
5. Keep tool descriptions under 200 characters

### New Documentation

- **`PROGRESSIVE_DISCLOSURE_GUIDE.md`** - Comprehensive architecture guide
- **`MCP_TOKEN_AUDIT_CHECKLIST.md`** - Practical optimization checklist
- **Context-Efficient Architecture** section in main best practices doc

## 🏷️ Shell Prompt Context

**Updated in v2.1.0:** Always-visible worktree context in your shell prompt.

### Why It Matters

When running multiple Claude Code sessions across worktrees, your shell prompt shows:
- Which project you're in
- Which issue or wave you're working on
- Automatic detection from branch name

### Quick Setup

Add to `~/.bashrc`:
```bash
mkdir -p ~/.claude/scripts
ln -sf ~/Projects/claude-power-pack/scripts/prompt-context.sh ~/.claude/scripts/
export PS1='$(~/.claude/scripts/prompt-context.sh)\w $ '
```

### Supported Branch Patterns

| Branch Pattern | Prompt Shows |
|----------------|--------------|
| `issue-42-auth` | `[CPP #42]` |
| `wave-5c.1-feature` | `[CPP W5c.1]` |
| `wave-5c-1-feature` | `[CPP W5c.1]` |
| `wave-3-cleanup` | `[CPP W3]` |
| `main` | `[CPP]` |

### Customization

Create `.claude-prefix` in project root to set custom prefix:
```bash
echo "NHL" > .claude-prefix
```

Otherwise, prefix is derived from repo name (e.g., `claude-power-pack` → `CPP`).

## 📋 Issue-Driven Development

**New in v1.7.0:** A methodology for managing complex projects with Claude Code.

### The Concept

Issue-Driven Development (IDD) combines:
- **Hierarchical Issues** - Phases → Waves → Micro-issues
- **Git Worktrees** - Parallel development without branch switching
- **Shell Prompt Context** - Visual context for current worktree
- **Structured Commits** - Traceable via "Closes #N"

### Quick Start

1. **Scan your project** — Run `/project-next` to analyze issues and get recommendations
2. **Start work** — `/flow:start 42` creates a worktree and branch automatically
3. **Your shell prompt** now shows the context:
   ```bash
   [CPP #42] ~/Projects/myrepo-issue-42 $
   ```
4. **Implement** the feature, then ship: `/flow:finish` → `/flow:merge`

Or use `/flow:auto 42` to automate the entire lifecycle in one shot.

### Documentation

- **[ISSUE_DRIVEN_DEVELOPMENT.md](ISSUE_DRIVEN_DEVELOPMENT.md)** - Full methodology guide
- **`/flow:help`** — All flow commands and conventions
- **`/project-next`** — Analyze issues and recommend next steps

### Key Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Branch | `issue-{N}-{description}` | `issue-123-auth-fix` |
| Worktree | `{repo}-issue-{N}` | `my-app-issue-123` |
| Commit | `type(scope): Desc (Closes #N)` | `fix(auth): Resolve bug (Closes #123)` |

## 🔄 Flow Workflow

**Since v4.0.0:** Stateless, git-native commands for the full issue lifecycle.

### The Golden Path

```
/flow:auto 42
  → creates worktree → analyzes issue → implements → commits → PR → merge → deploy
```

Or step-by-step:

```
/flow:start 42 → work → /flow:finish → /flow:merge → /flow:deploy
```

### Commands

| Command | Purpose |
|---------|---------|
| `/flow:start <issue>` | Create worktree and branch for an issue |
| `/flow:status` | Show active worktrees with issue and PR status |
| `/flow:check` | Run quality checks (lint, test, security) without committing |
| `/flow:finish` | Run quality gates (`make lint/test`), commit, push, create PR |
| `/flow:merge` | Squash-merge PR, clean up worktree and branch |
| `/flow:deploy [target]` | Run `make deploy` (if Makefile target exists) |
| `/flow:sync` | Push WIP branch to remote for cross-machine pickup |
| `/flow:auto <issue>` | Full lifecycle in one shot |
| `/flow:cleanup` | Prune stale worktree references and merged branches |
| `/flow:doctor` | Diagnose workflow environment and MCP server connectivity |
| `/flow:help` | Show all commands and conventions |

### Design Principles

- **Stateless** — All context from git (branches, worktrees, remotes) and GitHub (issues, PRs)
- **Idempotent** — Running `/flow:start 42` twice detects the existing worktree
- **Makefile-driven** — Quality gates and deployment use Makefile targets as the single source of truth
- **Safe cleanup** — `/flow:merge` handles worktree removal safely (avoids cwd-in-worktree issues)

### Makefile Integration

Flow commands auto-discover Makefile targets. Get started with the template:

```bash
cp ~/Projects/claude-power-pack/templates/Makefile.example Makefile
```

Or `/cpp:init` will offer to create one for you.

## 📋 Spec-Driven Development

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

# Sync feature to issues
python -m lib.spec_bridge sync user-auth
```

## 🔒 Session Coordination (Optional)

> **Moved to `extras/redis-coordination/` in v4.0.0.** Most users don't need this — the default `/flow` workflow is stateless and conflict-free for solo development.

For teams running multiple concurrent Claude Code sessions, optional coordination scripts and a Redis MCP server prevent conflicts (duplicate PRs, pytest interference, etc.).

### Coordination Tiers

| Tier | Mode | Description |
|------|------|-------------|
| **Local** (default) | `coordination: local` | Stateless. Context from git. No locking. |
| **Git** (optional) | `coordination: git` | State in `.claude/state.json`, synced via git. |
| **Redis** (teams) | `coordination: redis` | MCP server with distributed locks. |

See [`extras/redis-coordination/README.md`](extras/redis-coordination/README.md) for setup and usage.

## 📊 Project Commands

**New in v1.8.0:** Commands for project orientation and issue prioritization.

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

**Use when:** Starting a session, context is high, or you already know what to work on.

### /project-next

Full orchestrator for GitHub issue prioritization:
- Analyze open issues with hierarchy awareness (Wave/Phase patterns)
- Map worktrees to issues for context-aware recommendations
- Prioritize: Critical → In Progress → Ready → Quick Wins
- Set terminal labels for selected work

**Use when:** Unsure what to work on, need issue analysis, or want cleanup suggestions.

## 🐙 GitHub Issue Management

**New in v1.6.0:** Full CRUD operations for GitHub issues directly from Claude Code.

### Available Commands

| Command | Description |
|---------|-------------|
| `/github:help` | Overview of all GitHub commands |
| `/github:issue-list` | List and search issues with filters |
| `/github:issue-create` | Create issues with guided prompts |
| `/github:issue-view` | View issue details and comments |
| `/github:issue-update` | Update title, body, labels, add comments |
| `/github:issue-close` | Close issues with optional comment |

### Issue Templates

When creating issues via GitHub web UI, structured templates are available:

- **Best Practice Suggestion** - Share a new technique or tip
- **Documentation Correction** - Report errors or outdated info
- **Feature Request** - Request new commands/skills/capabilities
- **Bug Report** - Report bugs in MCP server or commands

### Quick Examples

```bash
# List open issues
/github:issue-list

# Create a new best practice suggestion
/github:issue-create

# View issue #42
/github:issue-view 42

# Close issue with comment
/github:issue-close 42
```

### Prerequisites

Requires GitHub CLI (`gh`) to be installed and authenticated:
```bash
gh auth status  # Check authentication
gh auth login   # Authenticate if needed
```

## 🔐 Secrets Management

Tiered secrets management scaling from `.env` files to AWS Secrets Manager, with audit logging and a FastAPI web UI.

### Features

- **Tiered Providers**: DotEnv global config (default) → AWS Secrets Manager (production)
- **Full CRUD**: Get, set, delete, list, rotate secrets per project
- **Output Masking**: Never exposes actual secret values
- **Audit Logging**: Actions logged to `~/.config/claude-power-pack/audit.log` (never values)
- **Secret Injection**: `creds run -- cmd` injects secrets as env vars
- **FastAPI Web UI**: Local-only management interface with bearer token auth

### Commands

| Command | Purpose |
|---------|---------|
| `/secrets:get [id]` | Get credentials (masked output) |
| `/secrets:set KEY VALUE` | Set or update a secret |
| `/secrets:delete KEY` | Delete a secret key (with confirmation) |
| `/secrets:list` | List all secret keys (values masked) |
| `/secrets:run -- CMD` | Run command with secrets injected as env vars |
| `/secrets:validate` | Test credential configuration |
| `/secrets:ui` | Launch web UI for management |
| `/secrets:rotate KEY` | Rotate a secret value |
| `/secrets:help` | Overview of all commands |

### CLI Usage

```bash
# Add lib to PYTHONPATH
export PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"

# Set a secret
python -m lib.creds set DB_PASSWORD my-secret-value

# Delete a secret
python -m lib.creds delete DB_PASSWORD

# List secrets (masked)
python -m lib.creds list

# Run command with secrets injected
python -m lib.creds run -- make deploy

# Validate all providers
python -m lib.creds validate
```

### Python Usage

```python
from lib.creds import get_bundle_provider
from lib.creds.project import get_project_id

provider = get_bundle_provider()
bundle = provider.get_bundle(get_project_id())
print(bundle)  # Keys visible, values masked
```

## 🐍 Python Environment (uv)

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

### pyproject.toml First (PEP 621 & PEP 723)

**Always use `pyproject.toml`** for Python projects. Never `setup.py`, `setup.cfg`, or `requirements.txt` for new projects.

- **PEP 621** — Standard `[project]` table in `pyproject.toml` for all project metadata and dependencies
- **PEP 723** — Inline `# /// script` metadata for single-file scripts (`uv run` auto-installs deps)
- **PEP 735** — `[dependency-groups]` for dev dependencies (replaces `requirements-dev.txt`)

```bash
uv init my-project           # Creates PEP 621 pyproject.toml
uv add requests              # Adds to [project.dependencies]
uv add --dev pytest          # Adds to [dependency-groups] dev
uv add --script s.py rich    # Adds inline PEP 723 metadata
```

See `docs/skills/python-packaging.md` for full PEP 621/723 reference with examples.

### Recommended Python Stack (uv-compatible)

| Category | Recommended | Avoid |
|----------|------------|-------|
| Package mgmt | `uv` | pip, poetry, conda |
| HTTP client | `httpx>=0.27` | requests (unless needed) |
| Validation | `pydantic>=2.6` | marshmallow, attrs |
| CLI | `typer>=0.12` or `click>=8.1` | argparse (for complex CLIs) |
| Web (API) | `fastapi>=0.115` | Flask (for API-only) |
| Web (full) | `django>=5.1` | Django <5.0 (uv conflicts) |
| Linting | `ruff>=0.8` | flake8, pylint, isort, black |
| Type checking | `mypy>=1.13` or `pyright` | — |
| Testing | `pytest>=8.3` | unittest |
| Build | `hatchling` or `setuptools>=75` | poetry-core |
| Task runner | `make` + `uv run` prefix | invoke, nox |

All commands should run through `uv run`:
```makefile
test:
	uv run pytest

lint:
	uv run ruff check .
```

Always commit `uv.lock` for reproducibility. Use `uv lock` to generate/update.

### Project Structure

Each Python component has its own `pyproject.toml`:
- `mcp-second-opinion/pyproject.toml`
- `mcp-playwright-persistent/pyproject.toml`
- `mcp-evaluate/pyproject.toml` (deprecated — kept for reference)
- `mcp-nano-banana/pyproject.toml`
- `extras/redis-coordination/mcp-server/pyproject.toml` (optional)
- `lib/creds/pyproject.toml`
- `lib/security/pyproject.toml`
- `lib/cicd/pyproject.toml`
- `lib/spec_bridge/pyproject.toml`

## 🛡️ Security Hooks

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

## 🔍 Security Scanning

Novice-friendly security vulnerability detection with `/flow` integration.

### Commands

| Command | Purpose |
|---------|---------|
| `/security:scan` | Full scan: native checks + available external tools |
| `/security:quick` | Quick scan: native checks only (zero deps, ~1 sec) |
| `/security:deep` | Deep scan: includes git history analysis |
| `/security:explain <ID>` | Detailed explanation of a finding type |
| `/security:help` | Overview of security commands |

### What's Checked

**Native (always available):**
- `.gitignore` coverage for sensitive file patterns
- File permissions on keys/secrets (chmod 600)
- High-confidence secrets: AWS keys, GitHub tokens, OpenAI/Anthropic keys
- `.env` files tracked by git
- Debug flags in production configs

**External (auto-detected, optional):**
- [gitleaks](https://github.com/gitleaks/gitleaks) — secrets in code + git history
- [pip-audit](https://pypi.org/project/pip-audit/) — Python dependency CVEs
- npm audit — Node.js dependency CVEs

### /flow Integration

Security scanning runs automatically as a quality gate:
- `/flow:finish` runs `/security:quick` before creating a PR
- `/flow:deploy` runs `/security:quick` before deploying
- CRITICAL findings block the gate; HIGH findings produce warnings

### Configuration

Customize gate behavior and suppress known findings via `.claude/security.yml`:

```yaml
gates:
  flow_finish:
    block_on: [critical]
    warn_on: [high]
suppressions:
  - id: HARDCODED_SECRET
    path: tests/fixtures/.*
    reason: "Test fixtures with fake credentials"
```

### CLI Usage

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security scan
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security explain HARDCODED_PASSWORD
```

## 🔧 CI/CD & Verification (Tier 4)

Framework-aware build system detection, verification, and deployment automation.

### Commands

| Command | Purpose |
|---------|---------|
| `/cicd:init` | Detect framework, generate Makefile and cicd.yml |
| `/cicd:check` | Validate Makefile against CPP standards |
| `/cicd:health` | Run health checks (endpoints + processes) |
| `/cicd:smoke` | Run smoke tests from cicd.yml |
| `/cicd:pipeline` | Generate GitHub Actions CI/CD workflows |
| `/cicd:container` | Generate Dockerfile and docker-compose.yml |
| `/cicd:help` | Overview of CI/CD commands |

### The Verification Loop

```
code → lint/test → deploy → health check → smoke test → report
```

The CI/CD system auto-detects your project's framework (Python, Node.js, Go, Rust) and generates appropriate Makefiles, GitHub Actions workflows, and container configurations. Health checks and smoke tests verify deployments work end-to-end.

### Configuration

Configure health checks and smoke tests in `.claude/cicd.yml`:

```yaml
health:
  endpoints:
    - url: http://localhost:8000/health
      name: API Server
      expected_status: 200
smoke_tests:
  - name: API responds
    command: "curl -sf http://localhost:8000/health"
    expected_exit: 0
```

### CLI Usage

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.cicd detect
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.cicd health
```

## 🧪 QA Testing

Config-driven automated web testing using Playwright MCP.

### Commands

| Command | Purpose |
|---------|---------|
| `/qa:test <target> [area]` | Run QA tests, log bugs as GitHub issues |
| `/qa:help` | Overview of QA commands |

### Quick Start

```bash
# Test a URL directly (no config needed)
/qa:test https://myapp.example.com

# Test using a shortcut from qa.yml
/qa:test myapp dashboard
```

### Configuration

Place `.claude/qa.yml` in your project to configure shortcuts, test areas, and test checklists:

```yaml
project:
  url: https://myapp.example.com
shortcuts:
  staging: https://staging.myapp.example.com
test_areas:
  login:
    path: /login
    description: "Authentication flow"
    tests:
      - "Login form renders"
      - "Form validation works"
```

Without config, `/qa:test` runs in interactive mode with generic testing. Requires the Playwright MCP server.

## 🎨 Documentation & Diagrams

Generate C4 architecture diagrams, professional visuals, and PowerPoint presentations using the Nano-Banana MCP server.

### Commands

| Command | Purpose |
|---------|---------|
| `/documentation:c4` | Generate C4 architecture diagrams (all 4 levels) |
| `/documentation:pptx [topic]` | Guided PowerPoint creation with optional diagrams |
| `/documentation:help` | Overview of documentation commands |

### Diagram Types

Architecture, c4, flowchart, sequence, orgchart, timeline, and mindmap — all rendered as self-contained HTML at 1920x1080.

### Setup

```bash
claude mcp add nano-banana --transport stdio -- uv run --directory ~/Projects/claude-power-pack/mcp-nano-banana python src/server.py --stdio
```

See `mcp-nano-banana/README.md` for full documentation.

## 📊 Evaluate Commands

Multi-model evaluation flow for structured decision-making.

### Commands

| Command | Purpose |
|---------|---------|
| `/evaluate:issue` | Full 4-phase evaluation: divergence, reasoning, validation, spec output |
| `/evaluate:help` | Overview of evaluate commands |

Uses the MCP Second Opinion server to consult multiple LLM models in parallel. Output lands in `.specify/specs/` as spec.md, plan.md, and tasks.md.

## ⚡ Session Initialization

**New in v1.1.0:** Auto-check for repository updates at session start.

A SessionStart hook (`./claude/hooks.json`) automatically checks if this repository has updates:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "bash -c 'cd /path/to/claude-power-pack && git fetch && ...'"
      }
    ]
  }
}
```

**Benefits:**
- Stay current with community best practices
- Minimal context footprint (~20 tokens)
- Automatic, hands-free
- Quick "up-to-date" confirmation or update prompt

## 📖 On-Demand Documentation

**New in v1.1.0:** Documentation loads only when needed to preserve context.

### Skills

- **`best-practices`** skill - Triggers on keywords like "best practices", "MCP optimization", "progressive disclosure"
  - Located: `.claude/skills/best-practices.md`
  - Loads full documentation only when relevant
  - ~150 tokens metadata vs ~5K+ when activated

### Slash Commands

- **`/load-best-practices`** - Load full community wisdom
- **`/load-mcp-docs`** - Load MCP server documentation

### Context Optimization

With these changes, repository baseline drops from 17% → <1% of context:

**Before:** Auto-load all documentation (~21K+ tokens)
**After:** Minimal `CLAUDE.md` (~200 tokens) + on-demand loading

## 📊 Raw Data Files

### JSON Data Archives
- `claudecode_top_month.json` - Top 100 posts from past month (238KB)
- `top_best_practices_month.json` - Detailed comments from top 8 posts (110KB)
- `claudecode_posts.json` - Initial 25 posts scraped (47KB)
- `best_practice_threads.json` - Comments from initial analysis (15KB)

## 🛠️ Reddit Scraping Tools

### Web Scraper (No API Required!)

```python
# Run the scraper
python scrape_reddit.py

# Or use in Python
from scrape_reddit import scrape_subreddit, scrape_post_comments

# Get top posts from past week
posts = scrape_subreddit("ClaudeCode", limit=50, sort="top", time_filter="week")

# Get comments from specific post
comments = scrape_post_comments("post_id_here", "ClaudeCode")
```

## 🔗 Key Community Resources

### Top Posts & Repositories

1. **"Claude Code is a Beast – Tips from 6 Months"** (685 upvotes)
   - Repository: https://github.com/diet103/claude-code-infrastructure-showcase
   - The #1 resource for Claude Code mastery

2. **Code-Mode (60% token savings)** (242 upvotes)
   - https://github.com/universal-tool-calling-protocol/code-mode

3. **Hooks Mastery**
   - https://github.com/disler/claude-code-hooks-mastery

4. **Skills Registry**
   - https://claude-plugins.dev/skills (6000+ public skills)

---

# MCP Servers

Claude Power Pack includes two core MCP servers and one optional extra:

| Server | Port | Purpose | Location |
|--------|------|---------|----------|
| [Second Opinion](#mcp-second-opinion-server) | 8080 | Multi-model code review | `mcp-second-opinion/` |
| [Playwright Persistent](#mcp-playwright-persistent-server) | 8081 | Browser automation | `mcp-playwright-persistent/` |
| [Sequential Thinking](#sequential-thinking-optional) | stdio | Structured step-by-step reasoning | `extras/sequential-thinking/` (optional) |
| [Coordination](#mcp-coordination-server-optional) | 8082 | Redis-backed distributed locking | `extras/redis-coordination/mcp-server/` (optional) |

---

## MCP Second Opinion Server

An advanced MCP server that provides AI-powered "second opinions" on challenging coding issues. **Now with multi-model support** - consult Google Gemini, OpenAI Codex, Anthropic Claude, and more simultaneously!

## 🌟 Key Features

- **Multi-Model Consultation**: Compare opinions from 15 different AI models in parallel
- **Three Providers**: Google Gemini 3.1, OpenAI (Codex 5.3, GPT-5.2, o3/o4-mini), Anthropic Claude (Sonnet, Haiku, Opus)
- **Interactive Commands**: `/second-opinion:start` for quick reviews, `/second-opinion:models` for full selection
- **Google Gemini**: Gemini 3.1 Pro Preview with automatic fallback to 2.5 Pro
- **Multi-Turn Sessions**: Maintain context across conversations
- **Agentic Tool Use**: Models can autonomously search the web and fetch documentation
- **Playwright Integration**: Excellent for debugging web UI issues with screenshots
- **Cost Tracking**: Per-session and daily limits with detailed breakdowns
- **Security Hardened**: SSRF protection, domain approval system

### Available Models

| Model Key | Display Name | Provider | Best For |
|-----------|-------------|----------|----------|
| `gemini-3-pro` | Gemini 3.1 Pro | Google | Comprehensive analysis |
| `gemini-2.5-pro` | Gemini 2.5 Pro | Google | Stable, proven |
| `claude-sonnet` | Claude Sonnet 4.6 | Anthropic | Fast, excellent for code review |
| `claude-haiku` | Claude Haiku 4.5 | Anthropic | Fastest Claude, cost-effective |
| `claude-opus` | Claude Opus 4.6 | Anthropic | Most capable Claude |
| `codex` | GPT-5.3 Codex | OpenAI | Default coding model |
| `codex-mini` | GPT-5.2 Codex | OpenAI | Cost-effective coding model |
| `o4-mini` | o4-mini | OpenAI | Fast reasoning |
| `o3` | o3 | OpenAI | Advanced reasoning (Codex agent) |
| `gpt-5.2` | GPT-5.2 | OpenAI | Latest GPT |
| `gpt-4o` | GPT-4o | OpenAI | Fast multimodal |
| `o1` | o1 | OpenAI | Advanced reasoning |

## 🚀 MCP Quick Start

### 1. Get API Keys

You need **at least one** API key (all three recommended for full multi-model comparison):

- **Gemini**: [Google AI Studio](https://aistudio.google.com/apikey) (free tier available)
- **OpenAI**: [OpenAI Platform](https://platform.openai.com/api-keys)
- **Anthropic**: [Anthropic Console](https://console.anthropic.com/settings/keys)

### 2. Set Up Environment

```bash
cd mcp-second-opinion

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create .env from template
cp .env.example .env
```

### 3. Configure API Keys

Edit `.env` with your API keys:

```bash
# .env file - NEVER commit this file!
GEMINI_API_KEY=your-gemini-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
```

> **Security Note**: The `.env` file is already in `.gitignore` and will not be committed to version control.

### 4. Start Server

**Option A: Manual start (for testing)**
```bash
cd mcp-second-opinion
./start-server.sh
# Or directly: uv run python src/server.py
```

**Option B: Systemd service (recommended for persistent use)**
```bash
cd mcp-second-opinion/deploy
./install-service.sh           # Install as user service (default)
systemctl --user enable mcp-second-opinion
systemctl --user start mcp-second-opinion
```

The install script auto-detects your installation paths and uv location. Options:
- `--user` - Install as user service (no sudo, starts on login)
- `--system` - Install as system service (requires sudo, starts on boot)
- `--generate-only` - Generate service file without installing

Check status: `systemctl --user status mcp-second-opinion`
View logs: `journalctl --user -u mcp-second-opinion -f`

### 5. Configure Claude Code

Add the MCP server using the Claude CLI:

```bash
claude mcp add second-opinion --transport sse --url http://127.0.0.1:8080/sse
```

Or manually create `.mcp.json` in your working directory (e.g., `~/Projects/.mcp.json`):
```json
{
  "mcpServers": {
    "second-opinion": {
      "type": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

> **Important:** The URL must include the `/sse` suffix. Without it, Claude Code's health check will fail.

Verify the server is configured:
```bash
claude mcp list
```

## 🎯 MCP Best Practices

### Using Playwright for Web Debugging

The MCP excels at analyzing Playwright screenshots for iterative debugging:

```python
from playwright.sync_api import sync_playwright
import base64

def capture_issue():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://example.com/buggy-page")
        page.click("#trigger-button")
        screenshot = page.screenshot(full_page=True)
        browser.close()
        return base64.b64encode(screenshot).decode()

# Send to Second Opinion
response = get_code_second_opinion(
    code=playwright_test_code,
    language="python",
    image_data=capture_issue(),
    issue_description="Button doesn't trigger modal"
)
```

### Iterative Investigation Workflow

1. **Create debugging session** for maintaining context
2. **Capture initial screenshot** showing the issue
3. **Apply suggested fix** from Gemini
4. **Re-capture and validate** the fix
5. **Continue iterating** until resolved
6. **Generate summary** of all fixes applied

## 📦 MCP Tools Overview

### 12 Available Tools

#### Multi-Model Consultation (NEW in v1.5.0)
1. **`list_available_models`** - See all models with availability status
2. **`get_multi_model_second_opinion`** - Consult 2+ models in parallel, compare responses

#### Single Model Analysis
3. **`get_code_second_opinion`** - Comprehensive code analysis (Gemini)
4. **`health_check`** - Verify server status and API key configuration

#### Multi-Turn Sessions
5. **`create_session`** - Start multi-turn consultation
6. **`consult`** - Send message in session
7. **`get_session_history`** - Retrieve conversation
8. **`close_session`** - End with cost summary
9. **`list_sessions`** - View all sessions

#### Domain Approval (SSRF Protection)
10. **`approve_fetch_domain`** - Approve URL fetching
11. **`revoke_fetch_domain`** - Revoke approval
12. **`list_fetch_domains`** - List approved domains

### Multi-Model Usage Example

```python
# Get opinions from multiple models
result = get_multi_model_second_opinion(
    code="def fibonacci(n): ...",
    language="python",
    models=["gemini-3-pro", "codex", "gpt-5.2"],
    issue_description="Is this implementation efficient?"
)

# Result contains responses from all models with cost tracking
for response in result["responses"]:
    print(f"{response['display_name']}: {response['response'][:200]}...")
print(f"Total cost: ${result['total_cost']}")
```

---

## MCP Playwright Persistent Server

Persistent browser automation with session management for testing and web interaction.

### Key Features

- **Persistent Sessions**: Browser sessions survive across tool calls
- **Multi-Tab Support**: Open, switch, and manage multiple tabs
- **Full Automation**: Click, type, fill, select, hover, screenshot
- **Headless/Headed**: Run with or without visible browser
- **PDF Generation**: Export pages to PDF (headless only)

### Setup

```bash
cd mcp-playwright-persistent

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Playwright browsers
uv run playwright install chromium

# Start server
./start-server.sh
```

### Add to Claude Code

```bash
claude mcp add playwright-persistent --transport sse --url http://127.0.0.1:8081/sse
```

### Available Tools (29 total)

| Category | Tools |
|----------|-------|
| **Session** | `create_session`, `close_session`, `list_sessions`, `get_session_info`, `cleanup_idle_sessions` |
| **Navigation** | `browser_navigate`, `browser_click`, `browser_type`, `browser_fill`, `browser_select_option`, `browser_hover` |
| **Tabs** | `browser_new_tab`, `browser_switch_tab`, `browser_close_tab`, `browser_go_back`, `browser_go_forward`, `browser_reload` |
| **Capture** | `browser_screenshot`, `browser_snapshot`, `browser_pdf`, `browser_get_content`, `browser_get_text` |
| **Query** | `browser_evaluate`, `browser_wait_for`, `browser_wait_for_navigation`, `browser_get_attribute`, `browser_query_selector_all` |

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

---

## Sequential Thinking (Optional)

Structured step-by-step reasoning with revision and branching. Provides a `sequentialthinking` tool that Claude calls iteratively to break down complex problems into numbered thought steps.

- **No API keys** - Purely local state tracking
- **No port** - Runs as stdio subprocess via npx
- **No Python** - Only requires Node.js 18+

### Install

```bash
claude mcp add --transport stdio --scope user sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking
```

Or select it during `/cpp:init` when prompted for optional extras.

See [`extras/sequential-thinking/README.md`](extras/sequential-thinking/README.md) for details.

---

## MCP Coordination Server (Optional)

> **Moved to `extras/redis-coordination/mcp-server/` in v4.0.0.** Only needed for teams running multiple concurrent Claude Code sessions.

Redis-backed distributed locking and session coordination. Provides 8 MCP tools for lock management, session tracking, and health checks.

### Quick Setup

```bash
cd extras/redis-coordination/mcp-server
cp .env.example .env
./start-server.sh

# Add to Claude Code
claude mcp add coordination --transport sse --url http://127.0.0.1:8082/sse
```

**Requires:** Redis server. See [`extras/redis-coordination/README.md`](extras/redis-coordination/README.md) for full documentation.

---

# Installation

## Complete Setup

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) - Modern Python package manager
- Git

#### Installing uv (if not already installed)

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### Step 1: Clone Repository

```bash
git clone https://github.com/cooneycw/claude-power-pack.git
cd claude-power-pack
```

### Step 2: MCP Server Setup

Each MCP server automatically manages its dependencies via `pyproject.toml`. Simply run the start script:

```bash
# MCP Second Opinion (port 8080)
cd mcp-second-opinion
cp .env.example .env  # Configure API keys
./start-server.sh

# MCP Playwright (port 8081)
cd mcp-playwright-persistent
uv run playwright install chromium  # First time only
./start-server.sh

# MCP Coordination (port 8082) — optional, for teams only
cd extras/redis-coordination/mcp-server
./start-server.sh
```

### Step 3: Configure API Keys

```bash
cd mcp-second-opinion
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

---

# GitHub Setup

## Creating Your Repository

### 1. Create GitHub Repository

Go to [GitHub](https://github.com/new) and create a new repository:
- Name: `claude-power-pack` (or your preference)
- Description: "Claude Code best practices and MCP second opinion server"
- Public or Private (your choice)
- Do NOT initialize with README (we already have one)

### 2. Push to GitHub

```bash
# If not already initialized
git init
git branch -m main

# Add all files
git add .

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Environment
.env
.env.local
*.env

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Project specific
*.json
!.env.example
node_modules/
.claude/
EOF

git add .gitignore

# Commit
git commit -m "Initial commit: Claude best practices and MCP second opinion server"

# Add remote
git remote add origin https://github.com/cooneycw/claude-power-pack.git

# Push
git push -u origin main
```

### 3. Repository Structure

After setup, your repository will have:

```
claude-power-pack/
├── docs/
│   ├── skills/                                 # Topic-focused best practices (~3K each)
│   │   ├── context-efficiency.md               # Token optimization
│   │   ├── session-management.md               # Session & plan mode
│   │   ├── mcp-optimization.md                 # MCP best practices
│   │   ├── python-packaging.md                  # PEP 621/723, pyproject.toml
│   │   └── ...                                 # 10 topic skills total
│   └── reference/
│       └── CLAUDE_CODE_BEST_PRACTICES_FULL.md  # Complete guide (25K tokens)
├── .specify/                                    # Spec-Driven Development
│   ├── memory/constitution.md                  # Project principles
│   ├── specs/                                  # Feature specifications
│   └── templates/                              # Spec, plan, tasks templates
├── mcp-second-opinion/                         # Port 8080 - Code review
│   └── src/server.py                           # 12 tools
├── mcp-playwright-persistent/                  # Port 8081 - Browser automation
│   └── src/server.py                           # 29 tools
├── extras/
│   ├── sequential-thinking/                    # Optional: structured reasoning
│   │   └── README.md                           # Setup & usage
│   └── redis-coordination/                     # Optional: distributed locking
│       ├── mcp-server/                         # Port 8082 - Redis locking (8 tools)
│       └── scripts/                            # Session coordination scripts
├── lib/
│   ├── secrets/                                # Secrets management
│   │   ├── cli.py                              # get, validate commands
│   │   └── providers/                          # AWS, env providers
│   └── spec_bridge/                            # Spec-to-Issue sync
│       ├── parser.py                           # Parse spec/tasks files
│       └── issue_sync.py                       # GitHub issue creation
├── templates/
│   └── Makefile.example                        # Starter Makefile for flow integration
├── scripts/
│   ├── prompt-context.sh                       # Shell prompt context
│   ├── hook-mask-output.sh                     # Secret masking
│   ├── hook-validate-command.sh                # Command validation
│   ├── secrets-mask.sh                         # Secrets pipe filter
│   └── worktree-remove.sh                      # Safe worktree removal
├── .claude/
│   ├── commands/
│   │   ├── flow/                               # Flow workflow (start, finish, merge, deploy, auto)
│   │   ├── cpp/                                # CPP wizard (init, status, help)
│   │   ├── spec/                               # Spec commands
│   │   ├── github/                             # GitHub issue management
│   │   ├── secrets/                            # Secrets commands
│   │   ├── env/                                # Environment commands
│   │   ├── project-next.md                     # Issue orchestrator
│   │   └── project-lite.md                     # Quick reference
│   ├── skills/                                 # Skill loaders
│   └── hooks.json                              # Session/security hooks
├── .github/ISSUE_TEMPLATE/                     # Structured templates
├── ISSUE_DRIVEN_DEVELOPMENT.md                 # IDD methodology
├── PROGRESSIVE_DISCLOSURE_GUIDE.md             # Context optimization
├── MCP_TOKEN_AUDIT_CHECKLIST.md                # Token efficiency
└── README.md                                    # This file
```

## 📈 Usage Statistics

- **Total Posts Analyzed:** 125+
- **Comments Analyzed:** 200+
- **Community Size:** r/ClaudeCode
- **Top Post Upvotes:** 685
- **Skills in Registry:** 6000+

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Contribution Ideas

- Update best practices with new community insights
- Add more MCP tools to the second opinion server
- Improve the Reddit scraper
- Create automated testing
- Add more documentation

## ⚠️ Important Security Notes

### For Claude Code Skills
- **Review skills before installing** - Skills can execute arbitrary code
- Use trusted sources only
- Check skill code, not just descriptions

### For Claude Code Hooks
- **Hooks execute shell commands** - Review all hooks in `.claude/hooks.json`
- **SessionStart hooks run automatically** - Every new session triggers these
- **UserPromptSubmit hooks see your prompts** - Be aware of what data flows through
- Scripts in `~/.claude/scripts/` should be reviewed before symlinking

### For MCP Second Opinion
- **Protect your API key** - Never commit .env files
- **Review domain approvals** - Only approve trusted domains
- **Monitor costs** - Set appropriate limits

### For Session Coordination Scripts (Optional, in `extras/`)
- **Scripts have shell access** - Review scripts in `extras/redis-coordination/scripts/` before installing
- **Lock files in `~/.claude/coordination/`** - Contain session metadata
- **Heartbeat data** - Tracks active sessions (local only, not transmitted)

## 📋 Disclosures & Legal

### Content Attribution

The best practices content in this repository is compiled from public posts on r/ClaudeCode. This is **community-sourced content**, not official Anthropic documentation.

- **Source**: r/ClaudeCode subreddit (100+ top posts analyzed)
- **Nature**: Community tips, experiences, and recommendations
- **Not affiliated with**: Anthropic (makers of Claude)

Original post authors are credited in the Acknowledgments section.

### API Usage

This repository includes tools that use third-party APIs:

| Service | Usage | Terms |
|---------|-------|-------|
| Google Gemini | MCP Second Opinion server | [Google AI Terms](https://ai.google.dev/terms) |
| OpenAI | Multi-model consultation | [OpenAI Terms](https://openai.com/policies/terms-of-use) |
| GitHub | Issue management commands | [GitHub Terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service) |

**You are responsible for**:
- API costs incurred through your usage
- Compliance with each service's terms
- Protecting your API keys

### Code License

The scripts, commands, and MCP server code in this repository are released under the MIT License. The compiled best practices content is provided for educational purposes with attribution to original authors.

## 📜 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

### Best Practices Contributors
- u/JokeGold5455 - 685-upvote Beast post
- u/rm-rf-rm - Best practices collation
- u/spences10 - Skills activation insights
- The entire r/ClaudeCode community

### Technology Credits
- Google Gemini team for the excellent API
- MCP community for the protocol specification
- FastMCP for the server framework
- Claude Code team at Anthropic

## 📞 Support

- **Issues**: Open an issue in this repository
- **Reddit**: r/ClaudeCode community
- **Gemini API**: [Google AI Studio](https://aistudio.google.com/apikey)

---

**Repository Version**: 5.0.0
**Last Updated**: March 2026
**Maintainer**: cooneycw

## What's New in v5.0.0

- **MCP Nano-Banana** - Diagram generation (7 types including C4) + PowerPoint creation via `/documentation:pptx`
- **Tier 4: CI/CD & Verification** - `lib/cicd/` with framework detection, Makefile generation, health/smoke testing, pipeline generation
- **Evaluate Flow** - `/evaluate:issue` for multi-model 4-phase evaluation with spec output
- **`/project:init`** - Zero-to-GitHub-repo scaffolding in one command
- **`/flow:check`** - Pre-commit quality validation (lint + test + security) without committing
- **QA testing** - Config-driven `/qa:test` with Playwright browser automation for any project
- **Django support** - Framework detection and `django-uv.mk` Makefile template
- **`/secrets:delete`** - Delete secrets with audit trail
- **211 unit tests** - Full test coverage for all Python libraries
- **Security gate docs** - Documented `/flow:finish` and `/flow:deploy` gate behavior
- **Stack-specific templates** - `/flow:doctor` suggests framework-appropriate Makefile templates

### Previous: v4.0.0

- **Flow commands** - `/flow:start`, `/flow:finish`, `/flow:merge`, `/flow:deploy`, `/flow:auto` for the full issue lifecycle
- **Stateless by default** - All context detected from git and GitHub, no locking needed for solo dev
- **Redis demoted to extras** - `mcp-coordination/` moved to `extras/redis-coordination/`
- **Streamlined hooks** - Removed session/heartbeat overhead from hooks.json
- **`/project-next` simplified** - Worktree-focused, recommends `/flow:start N` for next steps

### Previous: v3.0.0

- **Migrated to uv** - Replaced conda with uv for all Python dependency management
- **pyproject.toml** - All MCP servers and libraries now use pyproject.toml
- **Faster Setup** - Dependencies install automatically via `uv run`

### Previous: v2.8.0

- **CPP Initialization Wizard** - `/cpp:init` with tiered installation (Minimal/Standard/Full)
- **Spec-Driven Development** - `.specify/` structure with `/spec:*` commands
- **MCP Playwright Persistent** - 29 tools for browser automation (port 8081)
- **MCP Coordination Server** - Redis-backed distributed locking (port 8082)
- **Secrets Management** - `/secrets:*` commands with `lib/creds/` Python module
- **Security Hooks** - Secret masking and dangerous command blocking

### Previous: v2.2.0

- **MCP Coordination Server** - 8 Redis-backed tools for distributed locking
- **Wave/Issue Hierarchy** - Lock at issue, wave, or wave.issue level
- **Session Status Tiers** - Active/Idle/Stale/Abandoned with auto-expiry

### Previous: v2.1.0

- **Shell Prompt Context** - Replaced terminal labeling with PS1 integration
- **Wave Branch Support** - `[CPP W5c.1]` for wave branches

### Previous: v1.9.0

- **Session Coordination** - Prevent conflicts between concurrent Claude Code sessions
- **Lock System** - `session-lock.sh` for PR creation, pytest, and merge coordination

### Previous: v1.8.0

- **Project Commands** - `/project-lite` and `/project-next` for orientation

### Previous: v1.8.0

- **Gemini 3.1 Pro** - Upgrade from deprecated Gemini 3 Pro Preview
- **Codex 5.3 Default** - GPT-5.3 Codex as default, GPT-5.2 Codex as mini
- **o4-mini** - Fast reasoning model added (successor to o3-mini)

### Previous: v1.6.0

- **GitHub Issue Management** - Full CRUD via `/github:*` commands

### Previous: v1.5.0

- **Multi-Model Consultation** - Compare responses from 12 AI models in parallel
- **OpenAI Codex Support** - GPT-5.3 Codex / GPT-5.2 Codex

*Generated with [Claude Code](https://claude.ai/code)*