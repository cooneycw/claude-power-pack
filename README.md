# Claude Code Power Pack 🚀

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP 1.2.0+](https://img.shields.io/badge/MCP-1.2.0+-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive repository combining:
1. **Claude Code Best Practices** - Curated wisdom from the r/ClaudeCode community
2. **MCP Second Opinion Server** - AI-powered code review using Google Gemini 3 Pro

## 🎯 Quick Navigation

- [Claude Best Practices](#claude-best-practices) - Community insights & tips
- [Token-Efficient Tool Organization](#-token-efficient-tool-organization) - **NEW:** Progressive disclosure
- [Django Workflow Commands](#-django-workflow-commands) - **NEW:** Project setup & git worktrees
- [Session Initialization](#-session-initialization) - **NEW:** Auto-update checks
- [On-Demand Documentation](#-on-demand-documentation) - **NEW:** Context optimization
- [MCP Second Opinion](#mcp-second-opinion-server) - Gemini-powered code review
- [Installation](#installation) - Get started quickly
- [GitHub Setup](#github-setup) - Repository configuration

---

# Claude Best Practices

A comprehensive collection of Claude Code best practices compiled from the r/ClaudeCode community, based on 100+ top posts and thousands of upvotes.

## 📚 Best Practices Documents

### Main Guides

1. **[CLAUDE_CODE_BEST_PRACTICES_COMPREHENSIVE.md](CLAUDE_CODE_BEST_PRACTICES_COMPREHENSIVE.md)** ⭐ **START HERE**
   - Complete guide with insights from 100+ top posts
   - Based on posts with 600+ upvotes
   - Covers: Skills, Hooks, MCP, Session Management, Plan Mode, and more
   - 21KB of curated community wisdom

2. **[CLAUDE_CODE_BEST_PRACTICES.md](CLAUDE_CODE_BEST_PRACTICES.md)**
   - Earlier version with foundational tips
   - Good quick reference
   - 9.5KB

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

## 🐍 Django Workflow Commands

**New in v1.1.0:** Slash commands for Django project initialization and git worktree workflows.

### Available Commands

- **`/django:init`** - Create new Django project with modern best practices
  - Split settings (base/local/production)
  - Apps directory organization
  - Optional: DRF, Celery, Redis, Docker, CI/CD
  - Modern dependency management

- **`/django:worktree-setup`** - Configure git worktrees for dev/staging/production
  - Parallel environment development
  - Separate virtual environments per branch
  - Independent database configurations
  - No more branch switching!

- **`/django:worktree-explain`** - Educational guide on git worktrees
  - Detailed explanation with examples
  - Workflow scenarios (feature dev, hotfixes, deployment)
  - Troubleshooting and best practices
  - VSCode and tmux integration

### Setup

These commands are in `.claude/commands/django/`. To use them globally:

```bash
# Option 1: Symlink (recommended)
mkdir -p ~/.claude/commands
ln -s /path/to/claude-power-pack/.claude/commands/django ~/.claude/commands/django

# Option 2: Copy
cp -r .claude/commands/django ~/.claude/commands/
```

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

# MCP Second Opinion Server

An advanced MCP server that provides AI-powered "second opinions" on challenging coding issues using Google Gemini 3 Pro Preview.

## 🌟 Key Features

- **Powered by Gemini 3 Pro Preview**: Latest model with automatic fallback to Gemini 2.5 Pro
- **Multi-Turn Sessions**: Maintain context across conversations
- **Agentic Tool Use**: Gemini can autonomously search the web and fetch documentation
- **Playwright Integration**: Excellent for debugging web UI issues with screenshots
- **Cost Tracking**: Per-session and daily limits with detailed breakdowns
- **Security Hardened**: SSRF protection, domain approval system

## 🚀 MCP Quick Start

### 1. Get Gemini API Key
Get your free key from [Google AI Studio](https://aistudio.google.com/apikey)

### 2. Configure Environment
```bash
cd mcp-second-opinion
cp .env.example .env
# Add your GEMINI_API_KEY to .env
```

### 3. Start Server
```bash
python src/server.py
```

### 4. Configure Claude Code
Add to `~/.config/claude-code/config.json`:
```json
{
  "mcpServers": {
    "second-opinion": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/client-sse", "http://127.0.0.1:8080/sse"]
    }
  }
}
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

### 10 Available Tools

1. **`get_code_second_opinion`** - Comprehensive code analysis
2. **`health_check`** - Verify server status
3. **`create_session`** - Start multi-turn consultation
4. **`consult`** - Send message in session
5. **`get_session_history`** - Retrieve conversation
6. **`close_session`** - End with cost summary
7. **`list_sessions`** - View all sessions
8. **`approve_fetch_domain`** - Approve URL fetching
9. **`revoke_fetch_domain`** - Revoke approval
10. **`list_fetch_domains`** - List approved domains

---

# Installation

## Complete Setup

### Prerequisites
- Python 3.11+
- Conda (recommended) or pip
- Git

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/claude-power-pack.git
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
pip install mcp[cli]>=1.2.0 fastmcp>=1.0 google-generativeai>=0.3.0 \
           tenacity>=8.0.0 pydantic>=2.0.0 httpx>=0.24.0
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

# Add remote (replace with your repository URL)
git remote add origin https://github.com/yourusername/claude-power-pack.git

# Push
git push -u origin main
```

### 3. Repository Structure

After setup, your repository will have:

```
claude-power-pack/
├── README.md                                    # This file
├── CLAUDE_CODE_BEST_PRACTICES_COMPREHENSIVE.md # Main best practices guide
├── CLAUDE_CODE_BEST_PRACTICES.md              # Quick reference guide
├── scrape_reddit.py                           # Reddit scraper tool
├── fetch_reddit_posts.py                      # Alternative scraper
├── mcp-second-opinion/                        # MCP server directory
│   ├── src/                                   # Server source code
│   │   ├── server.py                         # Main server with 10 tools
│   │   ├── config.py                         # Configuration
│   │   ├── sessions.py                       # Session management
│   │   └── tools/                           # Agentic tools
│   ├── scripts/                              # Utility scripts
│   ├── deploy/                               # Deployment configs
│   ├── environment.yml                       # Conda environment
│   └── .env.example                         # Environment template
└── *.json                                    # Scraped data archives
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

### For MCP Second Opinion
- **Protect your API key** - Never commit .env files
- **Review domain approvals** - Only approve trusted domains
- **Monitor costs** - Set appropriate limits

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

**Repository Version**: 1.1.0 (Context-Efficient Architecture Update)
**Last Updated**: December 2024
**Maintainer**: Your Name Here

## What's New in v1.1.0

- **Progressive Disclosure Architecture** - Comprehensive guide with Anthropic's official data
- **Django Workflow Commands** - `/django:init`, `/django:worktree-setup`, `/django:worktree-explain`
- **Context Optimization** - 17% → <1% baseline with on-demand loading
- **MCP Token Audit Checklist** - Practical optimization guide
- **SessionStart Hook** - Auto-update checking
- **Best Practices Skill** - On-demand documentation loading
- **Enhanced Best Practices** - New Context-Efficient Tool Architecture section

*Generated with [Claude Code](https://claude.ai/code) via [Happy](https://happy.engineering)*