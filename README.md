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
- [Spec-Driven Development](#-spec-driven-development) - Specification workflow
- [Session Coordination](#-session-coordination) - Multi-session conflict prevention
- [Project Commands](#-project-commands) - `/project-lite` & `/project-next`
- [GitHub Issue Management](#-github-issue-management) - Full CRUD for issues
- [Secrets Management](#-secrets-management) - Secure credential access
- [Environment Commands](#-environment-commands) - Conda detection
- [Security Hooks](#-security-hooks) - Secret masking & command validation
- [MCP Servers](#mcp-servers)
  - [MCP Second Opinion](#mcp-second-opinion-server) - Multi-model code review (port 8080)
  - [MCP Playwright Persistent](#mcp-playwright-persistent-server) - Browser automation (port 8081)
  - [MCP Coordination](#mcp-coordination-server) - Redis-backed locking (port 8082)
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
| 2 | **Standard** | + Scripts, hooks, shell prompt, coordination |
| 3 | **Full** | + MCP servers (conda envs, API keys, systemd) |

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

1. **Scan your project** - Run `/project-next` to analyze issues
2. **Create a worktree** for the recommended issue:
   ```bash
   git worktree add -b issue-42-feature ../myrepo-issue-42
   cd ../myrepo-issue-42
   ```
3. **Your shell prompt** now shows the context automatically:
   ```bash
   [CPP #42] ~/Projects/myrepo-issue-42 $
   ```
4. **Implement and commit** with issue reference:
   ```bash
   git commit -m "feat: Add feature (Closes #42)"
   ```

### Documentation

- **[ISSUE_DRIVEN_DEVELOPMENT.md](ISSUE_DRIVEN_DEVELOPMENT.md)** - Full methodology guide
- **`/project-next`** command - Analyze issues and recommend next steps

### Key Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Branch | `issue-{N}-{description}` | `issue-123-auth-fix` |
| Worktree | `{repo}-issue-{N}` | `my-app-issue-123` |
| Commit | `type(scope): Desc (Closes #N)` | `fix(auth): Resolve bug (Closes #123)` |

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

## 🔒 Session Coordination

**New in v1.9.0:** Prevent conflicts between concurrent Claude Code sessions.

### Problem Solved

When running multiple Claude Code sessions (e.g., in tmux with worktrees):
- Sessions competing for PR creation
- pytest runs killed by other sessions
- No visibility into what other sessions are doing
- Worktree cleanup conflicts

### Quick Setup

```bash
# Symlink coordination scripts (adjust path to your clone location)
ln -sf /path/to/claude-power-pack/scripts/session-*.sh ~/.claude/scripts/
ln -sf /path/to/claude-power-pack/scripts/pytest-locked.sh ~/.claude/scripts/

# Create coordination directory
mkdir -p ~/.claude/coordination/{locks,sessions,heartbeat}
```

### Available Scripts

| Script | Purpose |
|--------|---------|
| `session-lock.sh list` | Show active locks |
| `session-lock.sh acquire NAME` | Acquire a named lock |
| `session-lock.sh release NAME` | Release a lock |
| `session-register.sh status` | Show active sessions |
| `pytest-locked.sh [args]` | Run pytest with coordination |

### Slash Commands

| Command | Purpose |
|---------|---------|
| `/coordination:pr-create` | Create PR with locking to prevent conflicts |
| `/coordination:merge-main BRANCH` | Merge to main with coordination |

### Hook Integration

Hooks automatically manage session lifecycle:
- **SessionStart**: Register session
- **UserPromptSubmit**: Update heartbeat
- **Stop**: Mark session as paused

See [ISSUE_DRIVEN_DEVELOPMENT.md](ISSUE_DRIVEN_DEVELOPMENT.md) for detailed documentation.

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

Secure credential access with provider abstraction and output masking.

### Features

- **Provider Abstraction**: AWS Secrets Manager + environment variables
- **Output Masking**: Never exposes actual secret values
- **Permission Model**: Read-only by default
- **Cross-Platform CLI**: Python CLI works on Windows/Mac/Linux

### Commands

| Command | Purpose |
|---------|---------|
| `/secrets:get [id]` | Get credentials (masked output) |
| `/secrets:validate` | Test credential configuration |

### CLI Usage

```bash
# Add lib to PYTHONPATH
export PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"

# Get database credentials (auto-detect provider)
python -m lib.creds get

# Validate all providers
python -m lib.creds validate
```

### Python Usage

```python
from lib.creds import get_credentials

creds = get_credentials()  # Auto-detects provider
print(creds)  # Password masked as ****
conn = await asyncpg.connect(**creds.dsn)  # dsn has real password
```

## 🌍 Environment Commands

Automatic conda environment detection on session start.

### Commands

| Command | Purpose |
|---------|---------|
| `/env:detect` | Show detected conda environment |

### Detection Priority

1. `CONDA_ENV_NAME` environment variable
2. `.conda-env` file in project root
3. `environment.yml` name field
4. Directory name matching conda env

### Usage

```bash
# Show detection info
~/.claude/scripts/conda-detect.sh --info

# Get activation command
~/.claude/scripts/conda-detect.sh --activate

# Run command in detected env
~/.claude/scripts/conda-detect.sh --run pytest tests/
```

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
| SessionStart | Session begins | Register, detect conda |
| UserPromptSubmit | Each prompt | Update heartbeat |
| PreToolUse (Bash) | Before command | Block dangerous operations |
| PostToolUse (Bash/Read) | After tool | Mask secrets in output |
| Stop | Session paused | Mark session paused |
| SessionEnd | Session ends | Release locks and claims |

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

Claude Power Pack includes three MCP servers for enhanced AI capabilities:

| Server | Port | Purpose |
|--------|------|---------|
| [Second Opinion](#mcp-second-opinion-server) | 8080 | Multi-model code review |
| [Playwright Persistent](#mcp-playwright-persistent-server) | 8081 | Browser automation |
| [Coordination](#mcp-coordination-server) | 8082 | Redis-backed distributed locking |

---

## MCP Second Opinion Server

An advanced MCP server that provides AI-powered "second opinions" on challenging coding issues. **Now with multi-model support** - consult Google Gemini, OpenAI Codex (GPT-5.1), and o3 simultaneously!

## 🌟 Key Features

- **Multi-Model Consultation**: Compare opinions from 10 different AI models in parallel
- **OpenAI Codex Support** (NEW in v1.5.0): GPT-5.1 Codex Max/Mini via Responses API
- **o3 Reasoning** (NEW in v1.5.0): Advanced reasoning model powering the Codex agent
- **Google Gemini**: Gemini 3 Pro Preview with automatic fallback to 2.5 Pro
- **Multi-Turn Sessions**: Maintain context across conversations
- **Agentic Tool Use**: Models can autonomously search the web and fetch documentation
- **Playwright Integration**: Excellent for debugging web UI issues with screenshots
- **Cost Tracking**: Per-session and daily limits with detailed breakdowns
- **Security Hardened**: SSRF protection, domain approval system

### Available Models

| Model Key | Display Name | Provider | Best For |
|-----------|-------------|----------|----------|
| `gemini-3-pro` | Gemini 3 Pro | Google | Comprehensive analysis |
| `gemini-2.5-pro` | Gemini 2.5 Pro | Google | Stable, proven |
| `gpt-4o` | GPT-4o | OpenAI | Fast multimodal, great for code |
| `gpt-4o-mini` | GPT-4o Mini | OpenAI | Fast, cost-effective |
| `gpt-4-turbo` | GPT-4 Turbo | OpenAI | Complex reasoning tasks |
| `codex-max` | Codex Max | OpenAI | Most capable for complex coding |
| `codex-mini` | Codex Mini | OpenAI | Cost-effective coding model |
| `o3` | o3 | OpenAI | Advanced reasoning (Codex agent) |
| `o1` | o1 | OpenAI | Advanced reasoning |
| `o1-mini` | o1 Mini | OpenAI | Faster reasoning model |

## 🚀 MCP Quick Start

### 1. Get API Keys

You need **at least one** API key (both recommended for multi-model comparison):

- **Gemini**: [Google AI Studio](https://aistudio.google.com/apikey) (free tier available)
- **OpenAI**: [OpenAI Platform](https://platform.openai.com/api-keys)

### 2. Set Up Environment

```bash
cd mcp-second-opinion

# Create environment
conda env create -f environment.yml
conda activate mcp-second-opinion

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
conda activate mcp-second-opinion
cd mcp-second-opinion/src
python server.py
```

**Option B: Systemd service (recommended for persistent use)**
```bash
cd mcp-second-opinion/scripts
./install-service.sh           # Install as user service (default)
systemctl --user enable mcp-second-opinion
systemctl --user start mcp-second-opinion
```

The install script auto-detects your installation paths and conda location. Options:
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
    models=["gemini-3-pro", "codex-max", "gpt-4o"],
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

## MCP Coordination Server

Redis-backed distributed locking for multi-session coordination.

### Key Features

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

### Available Tools (8 total)

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

### Lock Naming Conventions

```bash
# Auto-detect from branch
acquire_lock("work")          # issue-42-auth → issue:42
                              # wave-5c.1-feat → wave:5c.1

# Explicit locks
acquire_lock("issue:42")      # Issue-specific
acquire_lock("wave:5c")       # Wave-level
acquire_lock("pytest")        # Resource lock
```

### Session Status Tiers

| Status | Heartbeat Age | Meaning |
|--------|---------------|---------|
| 🟢 **Active** | < 5 min | Actively using Claude Code |
| 🟡 **Idle** | 5 min - 1 hour | Stepped away briefly |
| 🟠 **Stale** | 1 - 4 hours | Gone for extended period |
| ⚫ **Abandoned** | > 24 hours | Auto-released next day |

See `mcp-coordination/README.md` for detailed documentation.

---

# Installation

## Complete Setup

### Prerequisites
- Python 3.11+
- Conda (recommended) or pip
- Git

#### Installing Conda (if not already installed)

If you don't have conda installed, install Miniconda:

```bash
# Download and install Miniconda
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p $HOME/miniconda3

# Initialize conda for your shell
~/miniconda3/bin/conda init bash
source ~/.bashrc

# Accept Terms of Service (required for new installations)
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

For macOS, replace the download URL with:
```bash
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh -o /tmp/miniconda.sh
# Or for Apple Silicon:
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -o /tmp/miniconda.sh
```

### Step 1: Clone Repository

```bash
git clone https://github.com/cooneycw/claude-power-pack.git
cd claude-power-pack
```

### Step 2: Environment Setup

#### For Best Practices Tools Only:
```bash
conda create -n claude-power-pack python=3.11 -y
conda activate claude-power-pack
pip install requests  # For Reddit scraper
```

#### For MCP Second Opinion:
```bash
cd mcp-second-opinion
conda env create -f environment.yml
conda activate mcp-second-opinion
```

Or with pip:
```bash
pip install mcp[cli]>=1.2.0 fastmcp>=1.0 google-genai>=1.0.0 \
           openai>=1.50.0 tenacity>=8.0.0 pydantic>=2.0.0 httpx>=0.24.0
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
│   │   └── ...                                 # 9 topic skills total
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
├── mcp-coordination/                           # Port 8082 - Redis locking
│   └── src/server.py                           # 8 tools
├── lib/
│   ├── secrets/                                # Secrets management
│   │   ├── cli.py                              # get, validate commands
│   │   └── providers/                          # AWS, env providers
│   └── spec_bridge/                            # Spec-to-Issue sync
│       ├── parser.py                           # Parse spec/tasks files
│       └── issue_sync.py                       # GitHub issue creation
├── scripts/
│   ├── prompt-context.sh                       # Shell prompt context
│   ├── session-*.sh                            # Session coordination
│   ├── hook-mask-output.sh                     # Secret masking
│   ├── hook-validate-command.sh                # Command validation
│   ├── conda-detect.sh                         # Conda detection
│   └── worktree-remove.sh                      # Safe worktree removal
├── .claude/
│   ├── commands/
│   │   ├── cpp/                                # CPP wizard (init, status, help)
│   │   ├── spec/                               # Spec commands
│   │   ├── github/                             # GitHub issue management
│   │   ├── secrets/                            # Secrets commands
│   │   ├── env/                                # Environment commands
│   │   ├── coordination/                       # PR/merge coordination
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

### For Session Coordination Scripts
- **Scripts have shell access** - Review `session-*.sh` before installing
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

**Repository Version**: 2.8.0 (Full Documentation Update)
**Last Updated**: December 2025
**Maintainer**: cooneycw

## What's New in v2.8.0

- **CPP Initialization Wizard** - `/cpp:init` with tiered installation (Minimal/Standard/Full)
- **Spec-Driven Development** - `.specify/` structure with `/spec:*` commands
- **MCP Playwright Persistent** - 29 tools for browser automation (port 8081)
- **MCP Coordination Server** - Redis-backed distributed locking (port 8082)
- **Secrets Management** - `/secrets:*` commands with `lib/secrets/` Python module
- **Environment Commands** - `/env:detect` for conda environment detection
- **Security Hooks** - Secret masking and dangerous command blocking
- **Comprehensive README Update** - Full documentation of all features

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

### Previous: v1.6.0

- **GitHub Issue Management** - Full CRUD via `/github:*` commands

### Previous: v1.5.0

- **Multi-Model Consultation** - Compare responses from 10 AI models in parallel
- **OpenAI Codex Support** - GPT-5.1 Codex Max/Mini

*Generated with [Claude Code](https://claude.ai/code)*