# Claude Code Best Practices

*Compiled from r/ClaudeCode top posts (Past Month - November 2025)*

**Sources:** 100+ top posts from past month, including the #1 post with 685 upvotes

---

## 📑 Table of Contents

1. [Top Tips from Power Users](#top-tips-from-power-users)
2. [Skills System](#skills-system)
3. [CLAUDE.md Optimization](#claudemd-optimization)
4. [Avoiding Context Degradation](#avoiding-context-degradation)
5. [Spec-Driven Development](#spec-driven-development)
6. [MCP Best Practices](#mcp-best-practices)
7. [Context-Efficient Tool Architecture](#context-efficient-tool-architecture)
8. [Hooks & Automation](#hooks--automation)
9. [Shell Prompt Context](#shell-prompt-context)
10. [Issue-Driven Development](#issue-driven-development)
11. [Session Management](#session-management)
12. [Plan Mode](#plan-mode)
13. [Code Quality & Review](#code-quality--review)
14. [Workflow Patterns](#workflow-patterns)
15. [Build, Test & Deploy Patterns](#build-test--deploy-patterns)
16. [Python Packaging Standards](#python-packaging-standards)
17. [Common Pitfalls](#common-pitfalls)
18. [Tools & Resources](#tools--resources)

---

## Top Tips from Power Users

### From "Claude Code is a Beast" (685 upvotes, 6 months experience)

**Repository:** https://github.com/diet103/claude-code-infrastructure-showcase

**Key Insights:**

1. **Skills with Pattern Matching**
   - Use hooks to pre-fetch skills for activation
   - Skill = prompt injection + hook + pattern matching
   - This dramatically improves skill activation rates

2. **Multi-Agent Architecture**
   - Layer your agents for different concerns
   - Separate planning from execution
   - Use specialized agents for review

3. **Infrastructure as Code**
   - Treat your Claude Code setup like infrastructure
   - Version control everything (.claude directory)
   - Share reusable patterns across projects

4. **Development Environment Integration**
   - Use pm2 for process management
   - Integrate with your existing dev tooling
   - Make Claude Code part of your environment, not separate

**Community Response:**
- "99% of gripes, questions, and issues faced in this subreddit can be answered with this post"
- Praised as "CLAUDE CODE 101" masterpiece

---

## Skills System

### Improving Skill Activation Rates (214 upvotes)

**From "Claude Code skills activate 20% of the time. Here's how I got to 84%"**

**Problem:** Default skill activation is around 20%

**Solution:**

1. **Detailed, Context-Rich Skills**
   - Include specific examples and patterns
   - Provide detailed guides for SvelteKit, Svelte 5 runes, data flow patterns
   - More context = better activation

2. **Pattern Matching**
   - Skills need clear trigger patterns
   - Use specific terminology that matches your codebase
   - Make triggers unambiguous

3. **Regular Testing & Refinement**
   - Test skill activation regularly
   - Refine based on what triggers successfully
   - Remove or merge underperforming skills

### Skills Best Practices

**From Community Discussion:**

- **Skills = Prompt Injection**
  - At core, skills are just specialized prompts
  - Power comes from combining with hooks and patterns
  - Think of them as reusable context modules

- **Don't Overload**
  - 1-3 well-crafted skills better than 10 mediocre ones
  - Each skill should have clear, distinct purpose
  - Avoid overlap between skills

- **Version Control Skills**
  - Keep skills in git
  - Share successful patterns with team
  - Document what triggers each skill

**Registry:** https://claude-plugins.dev/skills (6000+ public skills)

---

## CLAUDE.md Optimization

### Optimized Prompts (+5-10% on SWE Bench)

**From "Optimized CLAUDE.md prompt instructions" (53 upvotes)**

**Key Finding:** You can significantly improve performance by optimizing CLAUDE.md

**Recommendations:**

1. **Experiment with System Prompts**
   - Don't accept defaults
   - Test different prompt formulations
   - Measure results on your specific use cases

2. **Include Project-Specific Context**
   - Architecture decisions
   - Coding standards
   - Common patterns in your codebase

3. **Be Explicit About Constraints**
   - What NOT to do
   - Token budgets
   - Performance requirements

### CLAUDE.md Tips (30 upvotes)

**From "CLAUDE.md tips" thread:**

1. **Structure Matters**
   - Use clear sections
   - Prioritize most important info at top
   - Use markdown formatting effectively

2. **Include Examples**
   - Show desired code style
   - Provide example workflows
   - Demonstrate edge cases

3. **Set Expectations**
   - Define quality bars
   - Specify test requirements
   - Clarify documentation needs

4. **Update Regularly**
   - CLAUDE.md should evolve with your project
   - Add learnings from mistakes
   - Remove outdated guidance

---

## Avoiding Context Degradation

### "How to avoid claude getting dumber (for real)" (47 upvotes)

**Problem:** Claude Code gets progressively worse during long sessions

**Root Cause:** Conversation compacting

**Solutions:**

1. **Avoid Compacting When Possible**
   - Each compact loses information
   - Start fresh session instead
   - Use git commits as natural break points

2. **Strategic Session Resets**
   - After completing major feature
   - When switching between different areas of codebase
   - If you notice quality degradation

3. **Context Files Instead of Conversation**
   - Store important context in files (CLAUDE.md, docs)
   - Don't rely on conversation history
   - Make context accessible via file reads

4. **Initialization Commands**
   - Use /prepare or similar to load fresh context
   - Keep context loading consistent
   - Document what context is needed for what tasks

---

## Spec-Driven Development

### "Why we shifted to Spec-Driven Development" (107 upvotes)

**Problem:** As features multiply, consistency and quality suffer

**Solution:** Spec-Driven Development (SDD)

**Approach:**

1. **Write Detailed Specs First**
   - Before any code
   - Include edge cases
   - Define success criteria

2. **Review Specs, Not Just Code**
   - Easier to fix design issues before coding
   - Specs are cheaper to iterate than code
   - Gets team alignment early

3. **Use Specs as Reference**
   - Claude can check code against spec
   - Automated verification possible
   - Clear acceptance criteria

4. **Iterate on Specs**
   - Specs are living documents
   - Update based on learnings
   - Version control specs like code

**Tools:**
- GitHub Spec Kit (mentioned but debated in community)
- Custom spec frameworks
- Markdown-based specs in repo

**Debate:** Some users question if SDD frameworks add real value vs overhead
- Works better for teams than solo developers
- May slow down rapid prototyping
- Best for complex, multi-person projects

---

## MCP Best Practices

### Code-Mode: Save >60% in tokens (242 upvotes)

**Repository:** https://github.com/universal-tool-calling-protocol/code-mode

**Key Innovation:** Execute MCP tools via code execution instead of direct calls

**Benefits:**
- 60% token savings
- More efficient MCP usage
- Less context bloat

### One MCP to Rule Them All (95 upvotes)

**From "no more toggling MCPs on/off":**

**Approach:** Use orchestrator MCP that manages other MCPs

**Benefits:**
- Don't need to enable/disable MCPs manually
- Intelligent routing to appropriate MCP
- Cleaner context

**Reference:** https://www.anthropic.com/engineering/code-execution-with-mcp

### MCP Selection

**Top MCPs Mentioned:**

1. **DevTools MCP** - Preferred over Playwright by some
2. **Playwright MCP** (`@playwright/mcp`) - Browser automation, UI testing
3. **Context 7** - Context management
4. **Supabase** - Database operations

**Installation Example:**
```bash
# Playwright MCP (official package from Microsoft)
claude mcp add playwright -- npx -y @playwright/mcp@latest
```

**Wisdom:**
- "MCP is king of token consumption"
- Choose 1-3 quality MCPs
- Many users prefer direct code over MCP
- MCPs work best with dedicated subagent instructions

### Converting MCP to Skills (175 upvotes)

**From "I've successfully converted 'chrome-devtools-mcp' into Agent Skills":**

**Why Convert:**
- Chrome-devtools-mcp is useful but token-heavy
- Skills can be more targeted and efficient
- Better control over when/how tools activate

**Approach:**
- Extract core functionality
- Create focused skills for specific use cases
- Maintain benefits while reducing token usage

---

## Context-Efficient Tool Architecture

### The Token Budget Reality

**Anthropic's Data (from official engineering blog):**

| Scenario | Token Consumption |
|----------|-------------------|
| Traditional tool loading (100 tools) | ~77K tokens |
| With Tool Search Tool | ~8.7K tokens |
| **Savings** | **85%** |

**Tool Selection Accuracy Impact:**

| Model | Without Tool Search | With Tool Search |
|-------|---------------------|------------------|
| Opus 4 | 49% | 74% |
| Opus 4.5 | 79.5% | 88.1% |

### Progressive Disclosure Principle

**Definition:** Load tool context in stages, not all at once.

**Three-Tier Pattern:**
1. **Tier 1 - Metadata** (~100 tokens): Name + brief description
2. **Tier 2 - Instructions** (<5K tokens): Full documentation when relevant
3. **Tier 3 - Assets** (variable): Scripts/files only when executing

This is how Anthropic's Skills system works internally.

### Practical Application

**For MCP Users:**
1. Use `/context` to audit token consumption
2. Disable unused MCP servers per session
3. Consolidate similar tools (4 search providers → 1 with parameter)
4. Keep descriptions under 200 characters

**For Skills Users:**
1. Structure skills for lazy loading
2. Put detailed instructions in body, not metadata
3. Use clear trigger patterns
4. Let the system load full content only when matched

**For Large Tool Libraries (10+ tools):**
1. Consider Tool Search Tool pattern
2. Mark infrequently-used tools as `defer_loading: true`
3. Keep only essential tools loaded by default

### When to Convert MCP → Skills

| Scenario | Recommendation |
|----------|----------------|
| Tool provides external data access | Keep as MCP |
| Tool teaches a procedure | Convert to Skill |
| Tool is used in every session | Keep loaded |
| Tool is used occasionally | Lazy load or Skill |
| Tool has verbose description | Optimize or convert |

### Red Flags for Token Bloat

- 🚩 MCP server consuming >20K tokens
- 🚩 More than 5 MCP servers enabled simultaneously
- 🚩 Tool descriptions >500 characters
- 🚩 Multiple tools with overlapping functionality
- 🚩 `/context` shows >40% used by tools before work begins

### MCP Token Optimization Techniques

**From Scott Spence's Production Optimization:**

1. **Consolidate Related Tools**
   ```
   Before: web_search_tavily, web_search_brave, web_search_kagi
   After:  web_search (provider: tavily|brave|kagi)
   ```

2. **Trim Verbose Descriptions**
   ```
   Before (87 tokens): "This tool allows you to search the web using
   various search engines. It supports multiple providers and returns
   results in a structured format with titles, URLs, and snippets..."

   After (12 tokens): "Search the web. Returns titles, URLs, snippets."
   ```

3. **Standardize Parameter Names**
   - Use `query` not `search_term`
   - Use `limit` not `max_results`
   - Use `provider` not `engine`

4. **Selective Activation**
   ```bash
   # Use mcpick for session-specific server selection
   npx mcpick

   # Or use Claude Code native commands
   /mcp disable github  # When not doing git work
   /mcp enable playwright  # When doing frontend work
   ```

**Real Results:**
- 20 tools → 8 tools (60% reduction)
- 8,551 tokens saved per session
- Same functionality maintained

**See also:** `PROGRESSIVE_DISCLOSURE_GUIDE.md` for comprehensive architecture guidance

---

## Hooks & Automation

### Hook System Deep Dive (85 upvotes)

**From "Claude Code hooks confuse everyone at first":**

**Key Resource:** https://github.com/disler/claude-code-hooks-mastery

**Hook Types & Uses:**

1. **SessionStart** - Load context, setup environment
2. **UserPromptSubmit** - Validate/enrich prompts before sending
3. **ToolUse** - Intercept or modify tool usage
4. **ToolResult** - Process outputs before Claude sees them
5. **SessionEnd** - Cleanup, logging

**Best Practices:**

- Understand lifecycle to avoid fighting execution flow
- Use hooks for automation, not control
- Keep hooks simple and fast
- Log hook activity for debugging

### Advanced Hook Usage

**Pattern Matching for Skills (from 685 upvote post):**
- Use hooks to pre-fetch relevant skills
- Match patterns in user prompts
- Automatically activate appropriate context

**Editor Integration:**
- Use Ctrl-G hook to launch custom tools
- Extend beyond just opening editor
- Hook into any workflow automation

---

## Shell Prompt Context

### Why Prompt Context Matters

When running multiple Claude Code sessions across worktrees, knowing which issue you're working on is critical. Shell prompt integration provides always-visible context directly in your prompt.

### Setup

Add to `~/.bashrc`:
```bash
# Symlink the script
mkdir -p ~/.claude/scripts
ln -sf ~/Projects/claude-power-pack/scripts/prompt-context.sh ~/.claude/scripts/

# Add to PS1
export PS1='$(~/.claude/scripts/prompt-context.sh)\w $ '
```

For Zsh (`~/.zshrc`):
```zsh
precmd() { PS1="$(~/.claude/scripts/prompt-context.sh)%~ %% " }
```

### How It Works

The script automatically detects:
1. **Project prefix** from `.claude-prefix` file or derived from repo name
2. **Issue number** from branch name (pattern: `issue-{N}-*`)

### Example

```bash
# In worktree on branch issue-42-auth-flow
[NHL #42] ~/Projects/nhl-api-issue-42 $

# In main repo on main branch
[NHL] ~/Projects/nhl-api $

# Not in a git repo (no output)
~/Downloads $
```

### Customization

Create `.claude-prefix` in project root:
```bash
echo "NHL" > .claude-prefix
```

Otherwise, prefix is derived from repo name:
- `nhl-api` → `NHL`
- `claude-power-pack` → `CPP`

---

## Issue-Driven Development

Issue-Driven Development (IDD) is a workflow pattern that combines:
- **Hierarchical Issues** - Phases → Waves → Micro-issues
- **Git Worktrees** - Parallel development without branch switching
- **Terminal Labeling** - Visual context for multiple sessions
- **Structured Commits** - Traceable, closeable commits via "Closes #N"

### The Three-Level Hierarchy

```
Phase (Epic)
├── Wave (Feature Group)
│   ├── Micro-Issue (Atomic Task)
│   └── Micro-Issue
└── Wave
    └── Micro-Issue
```

### Why It Works with Claude Code

| Problem | IDD Solution |
|---------|--------------|
| Feature too large | Break into micro-issues |
| Lost context | Each issue has acceptance criteria |
| Parallel work blocked | Git worktrees enable concurrent development |
| No traceability | Commits link to issues via "Closes #N" |

### Key Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Branch | `issue-{N}-{description}` | `issue-123-player-landing` |
| Worktree | `{repo}-issue-{N}` | `nhl-api-issue-123` |
| Commit | `type(scope): Desc (Closes #N)` | `feat(api): Add endpoint (Closes #42)` |

### Getting Started

Use the `/project-next` command to analyze your repository's issues and get prioritized recommendations for what to work on next.

**Full documentation:** See [ISSUE_DRIVEN_DEVELOPMENT.md](ISSUE_DRIVEN_DEVELOPMENT.md) for the complete methodology guide including:
- Micro-issue templates
- Git worktree commands
- Multi-agent coordination patterns
- Best practices and anti-patterns

---

## Session Management

### The Single Most Useful Line (98 upvotes)

**From "The single most useful line for getting what you want from Claude Code":**

```
"Please let me know if you have any questions before making the plan!"
```

**Why It Works:**
- Forces Claude to clarify ambiguities upfront
- Prevents wasted work on wrong assumptions
- Creates dialogue before execution
- Especially powerful in Plan Mode

**Extension:**
- "Tell me if anything is unclear before proceeding"
- "What additional information do you need?"
- "Identify any assumptions you're making"

### When to Reset Sessions

**Patterns from Community:**

1. **Feature-Based** (most common)
   - One session per feature
   - Fresh start after git commit
   - Clear success criteria per session

2. **Time-Based**
   - Every 5-10 messages
   - After 1-2 hours of work
   - When reaching 60% context

3. **Quality-Based**
   - When Claude seems "confused"
   - After multiple failed attempts
   - When suggestions become repetitive

4. **Never Reset** (for some users)
   - If you have good tests and conventions
   - Context degradation less of issue
   - Continuous work style

### Context Management Patterns

**Initialization Context (from multiple sources):**

1. Create `/prepare` command
2. Load from memory bank (markdown files)
3. Include recent git history
4. Load relevant docs

**Memory Bank Structure:**
- Project overview
- Architecture decisions
- Current priorities
- Known issues
- Coding standards

---

## Plan Mode

### Use Plan Mode by Default (72 upvotes)

**From "4 Claude Code CLI tips I wish I knew earlier":**

**Benefits:**
- 20-30% better results
- Reduces wasted prompts
- Creates accountability
- Forces thinking before acting

**Enhanced Plan Mode** (37 upvotes)

**From "I made a better version of Plan Mode":**
- Custom plan mode implementations
- More detailed planning phases
- Integration with issue tracking

**Official Updates:**
- Claude Code 2.0.31 introduced new Plan subagent
- Enhanced subagent capabilities
- Better plan quality

---

## Code Quality & Review

### Production-Ready Software (76 upvotes)

**From "This is how I use the Claude ecosystem to actually build production-ready software":**

**Key Insight:** "You are the issue, not the AI"

**Approach:**

1. **Clear Requirements**
   - Be specific about what you want
   - Include edge cases
   - Define quality standards

2. **Iterative Review**
   - Don't accept first output
   - Ask for improvements
   - Challenge assumptions

3. **Test-Driven**
   - Write tests first
   - Verify behavior
   - Regression protection

4. **Use Multiple Claude Tools**
   - Claude Code for implementation
   - Claude.ai for design discussions
   - Different tools for different phases

### Review Patterns

**Pre-Code Review with GPT-4:**
- Use Codex to verify requirements
- Check for missed details
- Ensure specification compliance

**Self-Review:**
- Ask Claude to review its own code
- Have it identify potential issues
- Explain design decisions

---

## Workflow Patterns

### Parallel Agents (32 upvotes)

**From "Anyone else do this parallel agent hail mary":**

**When:** Stuck on difficult problem

**Approach:**
- Spawn multiple agents with different approaches
- Let them work in parallel
- Pick best solution

**Note:** Token-intensive but surprisingly effective

### tmux as Orchestration (59 upvotes)

**From "Using tmux as a bootleg orchestration system":**

**Setup:**
- Multiple Claude Code sessions in tmux
- Each pane handles different concern
- Cross-session coordination

**Benefits:**
- Separate contexts for separate tasks
- Easy switching between sessions
- Visual organization

### Multi-Instance Setup (39 upvotes)

**From "Run 2 (or even more) instances of Claude Code in parallel":**

**Use Cases:**
- Frontend + Backend simultaneously
- Different branches
- Experimentation vs production work

**Technical:**
- Separate working directories
- Different credential profiles
- Process isolation

---

## Build, Test & Deploy Patterns

### Makefile as the Canonical Interface

The `/flow` workflow treats the Makefile as the single source of truth for build, test, lint, and deploy operations. This decouples Claude Code commands from project-specific tooling.

**Why Makefile:**
- Universal — works across all project types (Python, Node, Rust, mixed)
- Declarative — targets and dependencies are explicit
- Discoverable — `grep -E '^[a-zA-Z_-]+:' Makefile` lists all available operations
- Composable — targets can depend on other targets, building dependency chains
- `/flow:finish` auto-discovers `lint` and `test` targets
- `/flow:deploy` runs any Makefile target by name
- `/flow:doctor` reports which standard targets are present

**Standard targets for flow integration:**

| Target | Used By | Purpose |
|--------|---------|---------|
| `lint` | `/flow:finish` | Code linting (auto-discovered) |
| `test` | `/flow:finish` | Test suite (auto-discovered) |
| `format` | Manual | Code formatting |
| `deploy` | `/flow:deploy` | Production deployment (default target) |
| `deploy-staging` | `/flow:deploy staging` | Staging deployment |
| `clean` | Manual | Remove build artifacts |

**Example Makefile with dependency chain:**

```makefile
.PHONY: test lint format deploy deploy-staging clean check

## Quality gates — used by /flow:finish
lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest

## Pre-deploy validation
check: lint test

## Deployment — used by /flow:deploy
deploy: check
	@echo "Deploying to production..."
	# Your deploy commands here

deploy-staging:
	@echo "Deploying to staging..."
	# Your staging deploy commands here

## Utilities
clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info
```

**Key practices:**
1. Always declare `.PHONY` for non-file targets
2. Use dependency chains (`deploy: check`) to enforce quality gates
3. Prefix informational output with `@` to reduce noise
4. Keep deploy logic in the Makefile, not scattered across scripts
5. Use the CPP template as a starting point: `cp ~/Projects/claude-power-pack/templates/Makefile.example Makefile`

### uv as the Python Environment Manager

[uv](https://docs.astral.sh/uv/) is the recommended Python dependency manager for Claude Code projects. It replaces pip, virtualenv, and pyenv with a single fast tool.

**Why uv:**
- 10-100x faster than pip for dependency resolution
- Automatic virtual environment management (no manual `venv` activation)
- Lock file support (`uv.lock`) for reproducible builds
- Drop-in replacement: `uv run pytest` instead of `pytest`
- Used by all CPP MCP servers internally

**uv + Makefile integration:**

All Makefile commands should use `uv run` to ensure correct environment:

```makefile
# Good — uses uv for isolation
test:
	uv run pytest

# Bad — relies on system Python or manual venv activation
test:
	pytest
```

**Quick start:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize a project (creates pyproject.toml)
uv init

# Add dependencies
uv add pytest ruff

# Run commands (auto-creates venv, installs deps)
uv run pytest
uv run ruff check .
```

### Retrospective Improvement

When deployments or builds fail repeatedly, use `/self-improvement:deployment` to analyze error patterns and propose Makefile improvements. This closes the feedback loop:

```
/flow:deploy -> fails -> /self-improvement:deployment -> fix Makefile -> /flow:deploy -> succeeds
```

See also: `templates/Makefile.example` for the CPP starter template.

---

## Python Packaging Standards

### Always Use pyproject.toml (PEP 621)

[PEP 621](https://peps.python.org/pep-0621/) is the official standard for declaring Python project metadata. **Every new Python project should use `pyproject.toml` with a `[project]` table.** Never create `setup.py`, `setup.cfg`, or `requirements.txt` for new projects.

| Legacy Approach | Modern Standard |
|----------------|-----------------|
| `setup.py` | `pyproject.toml` `[project]` table |
| `setup.cfg` | `pyproject.toml` `[project]` table |
| `requirements.txt` | `[project.dependencies]` + `uv.lock` |
| `requirements-dev.txt` | `[dependency-groups]` (PEP 735) |

**Minimal pyproject.toml:**

```toml
[project]
name = "my-project"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.8"]
```

**Key rules:**
1. **Always declare `requires-python`** — constrains dependency resolution
2. **Use `>=` lower bounds, not `==` pins** — the lockfile handles exact pinning
3. **Dev tools go in `[dependency-groups]`** (PEP 735), not `[project.optional-dependencies]`
4. **`[project.optional-dependencies]`** is for end-user extras (e.g., `pip install lib[postgres]`)
5. **Commit `uv.lock`** for applications — ensures reproducible installs
6. **Use `hatchling`** as default build backend — lightweight, standards-compliant

**uv commands:**
```bash
uv init my-project              # Creates PEP 621 pyproject.toml
uv add requests                 # Adds to [project.dependencies]
uv add --dev pytest ruff        # Adds to [dependency-groups] dev
uv add --group lint ruff        # Named dependency group
uv lock                         # Generate/update uv.lock
```

### Inline Script Metadata (PEP 723)

[PEP 723](https://peps.python.org/pep-0723/) embeds dependencies directly in single-file Python scripts. When `uv run` encounters a script with a `# /// script` block, it auto-installs dependencies in an ephemeral environment — no `pyproject.toml`, no `venv`, no `pip install`.

**Example:**

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests>=2.28",
#   "rich>=13.0",
# ]
# ///

import requests
from rich.pretty import pprint

resp = requests.get("https://api.example.com/data")
pprint(resp.json())
```

**Run it:** `uv run script.py` — dependencies installed automatically.

**Self-executing scripts (Unix):**
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
```

Then: `chmod +x script.py && ./script.py`

**Managing inline dependencies:**
```bash
uv init --script new.py         # Create script with metadata block
uv add --script script.py rich  # Add dependency to existing script
uv lock --script script.py      # Create script.py.lock for reproducibility
```

### When to Use Which

| Scenario | Standard | Why |
|----------|----------|-----|
| Multi-file project | PEP 621 (`pyproject.toml`) | Full packaging, dev groups, entry points |
| Library/package | PEP 621 (`pyproject.toml`) | Installable, extras, build system |
| Single-file utility script | PEP 723 (inline `# /// script`) | Self-contained, copy-paste ready |
| Gist or tutorial code | PEP 723 (inline) | No repo needed |
| MCP servers, web apps | PEP 621 (`pyproject.toml`) | Multiple modules, services |

**Rule of thumb:** If someone should be able to run it without cloning a repo, use PEP 723. Otherwise, use PEP 621.

### Anti-Patterns

| Anti-Pattern | Do This Instead |
|-------------|-----------------|
| `setup.py` for new projects | `pyproject.toml` `[project]` table |
| `pip freeze > requirements.txt` | `uv lock` (captures only direct deps properly) |
| `pip install -e .` | `uv sync` |
| Manual `venv` activation | `uv run <command>` |
| Deps in both `requirements.txt` and `pyproject.toml` | Single source of truth: `pyproject.toml` |

---

## Common Pitfalls

### Things That Make Claude "Dumber"

1. **Long Sessions Without Reset**
   - Compacting loses information
   - Contradictory context builds up
   - Fresh start often better

2. **Unclear Requirements**
   - Vague prompts = vague results
   - Missing edge cases
   - Assumed knowledge

3. **Fighting Claude's Patterns**
   - Let it use familiar patterns
   - Don't force unusual approaches
   - Work with defaults, not against

4. **Over-Reliance on Conversation History**
   - Put important info in files
   - Don't trust compacted history
   - Document decisions

### Warning: Malware in Skills (80 upvotes)

**From "Be careful with people spreading Claude Code Skills as malware on Github":**

**Risk:** Skills can execute arbitrary code

**Protection:**
- Review skills before installing
- Use trusted sources only
- Check skill code, not just description
- Be wary of skills from unknown authors

---

## Tools & Resources

### Essential Tools

**Task Management:**
- Markdown Task Manager: https://reddit.com/r/ClaudeCode/comments/1ot8nh2 (100 upvotes)
- Beads (issue tracker)
- Custom .claude/active/ folder system

**Switching Tools:**
- Clother - Switch between GLM, Kimi, Minimax, Anthropic endpoints
  https://github.com/jolehuit/clother

**Model Alternatives:**
- Gemini 3 Pro via gemini-cli
  https://github.com/forayconsulting/gemini_cli_skill
- Kimi K2 Thinking model integration
- GLM endpoint (but lacks web search)

**Skill Resources:**
- claude-plugins.dev (6000+ skills)
- Superpowers plugin: https://github.com/obra/superpowers
- Prompt Coach skill (analyzes prompt quality)

### Key Repositories

1. **Infrastructure Showcase** (from 685 upvote post)
   https://github.com/diet103/claude-code-infrastructure-showcase

2. **Hooks Mastery**
   https://github.com/disler/claude-code-hooks-mastery

3. **Code-Mode (60% token savings)**
   https://github.com/universal-tool-calling-protocol/code-mode

4. **Chrome DevTools as Skills**
   (converted from MCP - 175 upvotes)

### Official Updates

**Recent Claude Code Releases:**
- 2.0.27 - Claude Code on Web
- 2.0.31 - New Plan subagent
- 2.0.36 - Web enhancements
- 2.0.41 - UX improvements
- 2.0.50 - Latest with enhanced features

**Free Credits:**
- $1000 free usage for Pro/Max on CC Web (temporary)
- Credits reset behavior has been buggy
- May count against weekly limits

---

## Advanced Patterns

### Spec-First → Sandbox → Production

**From 685 upvote post + community:**

1. **Write Spec**
   - Detailed requirements
   - Edge cases
   - Success criteria

2. **Sandbox Testing** (Sonnet)
   - Separate directory for experiments
   - Verify key parts work
   - Try uncertain approaches

3. **Implementation** (Opus for complex, Sonnet for standard)
   - Cut-and-dry based on verified plan
   - Minimal decisions needed
   - Fast execution

4. **Review & Refine**
   - Test against spec
   - Iterate if needed
   - Git commit

### Multi-Repo Management

**From "perfect multi-repo-multi-model Code agent workspace":**

- Separate Claude Code instances per repo
- Model selection based on task type
- Coordination via shared documentation
- Flowchart for decision making

### Progressive Enhancement

**Pattern from Community:**

1. **Claude Prototype** - Get something working
2. **Vibe Code** - Iterate on feel/UX
3. **Freelancer Finish** - Professional polish

**Alternative:** All-Claude if quality standards maintained

---

## Best Practices Summary

### Top 10 Rules

1. **Use Plan Mode by default** - Ask Claude to clarify before acting
2. **Reset sessions frequently** - After features, at 60% context, or when quality drops
3. **Store context in files, not conversations** - CLAUDE.md, docs, specs
4. **Choose 1-3 quality MCPs** - More isn't better; efficiency matters
5. **Write detailed specs first** - Especially for complex work
6. **Use hooks for automation** - Pre-fetch skills, validate prompts
7. **Skills need good activation patterns** - Detailed, context-rich, specific triggers
8. **Review skills before installing** - Security risk from untrusted sources
9. **Optimize CLAUDE.md for your project** - Experiment, measure, iterate
10. **Work with Claude's strengths** - Familiar patterns, clear requirements, iterative refinement

### Red Flags

- 🚩 Context >60% and starting new complex feature
- 🚩 Claude giving contradictory advice
- 🚩 Repetitive failures on same task
- 🚩 Ignoring requirements you clearly stated
- 🚩 Taking approaches you explicitly rejected
- 🚩 Installing skills from unknown sources

### Green Flags

- ✅ Claude asks clarifying questions before proceeding
- ✅ Proposes multiple approaches and explains tradeoffs
- ✅ References your existing code patterns
- ✅ Suggests tests for new functionality
- ✅ Explains architectural decisions
- ✅ Admits when uncertain

---

## Model-Specific Notes

### Sonnet 4.5

**Strengths:**
- General purpose
- Good balance of cost/quality
- "Monster" for most tasks

**1M Context vs 200K:**
- Debate in community about actual benefits
- Some users see improvements
- Others see no difference
- May depend on use case

### Haiku 4.5

**When to Use:**
- Burn through limits slower
- Simple, well-defined tasks
- Documentation
- Code review

**Data from Pro user:**
- Significantly better token efficiency
- Acceptable quality for many tasks
- Good for extending weekly limits

### Opus

**When to Use:**
- Complex architectural decisions
- Planning phase
- Novel problems
- When quality > cost

### Alternative Models

**Gemini 3 Pro:**
- Via gemini-cli
- Competitive performance
- Different strengths/weaknesses

**Kimi K2 Thinking:**
- Impressive benchmarks
- Thinking/reasoning model
- Integration available

---

## Community Insights

### On AI-Assisted Development

**From experienced developers:**

> "Seasoned developers *embracing* AI tools, not shrugging them off as 'stupid' or 'a threat'. This is exactly the way."

> "You are the issue, not the AI" - Most complaints about AI code quality stem from unclear requirements

> "Claude is basically the world's dumbest junior engineer" - Set expectations accordingly

### On Learning Curve

**Progression:**
1. Fighting with Claude (week 1-2)
2. Learning to communicate (month 1)
3. Building infrastructure (months 2-3)
4. Optimization and mastery (months 4-6)

**Key Turning Point:** When you stop trying to control Claude and start collaborating

### On Productivity

**Mixed Reports:**

**Positive:**
- 10x productivity on greenfield projects
- Great for prototyping
- Excellent for exploration

**Realistic:**
- Not faster than expert on familiar tasks
- Saves time on unfamiliar tech
- Better for breadth than depth

**The Real Value:**
> "I don't think it writes better code than me... But I can just sit here and watch football and occasionally give direction" - Doing more with less active work

---

## Document Metadata

**Compiled:** November 2025
**Sources:**
- 100+ top posts from r/ClaudeCode (past month)
- 200+ comments analyzed
- Primary source: 685-upvote "Beast" post
- Secondary sources: 214-upvote skills post, 117-upvote best practices collation

**Update Frequency:** This represents November 2025 state of community knowledge. Claude Code evolves rapidly, so check recent posts for latest practices.

**Contributing:** This is a living document. Feel free to add your own learnings and share back with the community.

---

## Acknowledgments

Special thanks to the r/ClaudeCode community contributors:
- u/JokeGold5455 (Beast post)
- u/rm-rf-rm (Best practices collation v2)
- u/spences10 (Skills activation)
- u/daaain (Single most useful line)
- u/cryptoviksant (Avoiding context degradation)
- u/NumbNumbJuice21 (CLAUDE.md optimization)
- u/eastwindtoday (Spec-driven development)
- u/juanviera23 (Code-mode)
- And hundreds of other community members sharing their experiences

---

*End of Guide*

For latest updates, join r/ClaudeCode and sort by "Top" → "This Month"
