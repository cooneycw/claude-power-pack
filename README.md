# Claude Power Pack

A productivity toolkit for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds workflow automation, MCP servers, security scanning, secrets management, and CI/CD integration.

## What It Does

- **Workflow commands** (`/flow:auto`, `/flow:start`, `/flow:finish`) - Issue-driven development with worktrees, quality gates, and automated PR lifecycle
- **MCP servers** - Three containerized servers extending Claude Code's capabilities:
  - **Second Opinion** (port 8080) - Code review via external LLMs (Gemini, OpenAI, etc.)
  - **Playwright Persistent** (port 8081) - Browser automation with 29 tools
  - **Nano Banana** (port 8084) - Diagram generation and PowerPoint creation
- **Security scanning** (`/security:scan`) - Native vulnerability detection with git history analysis
- **Secrets management** (`/secrets:*`) - Tiered credential storage (dotenv, env-file, AWS Secrets Manager) with audit logging and a web UI
- **CI/CD integration** (`/cicd:*`) - Framework detection, Makefile generation, health checks, and IaC scaffolding
- **Project scaffolding** (`/project:init`) - Zero-to-GitHub-repo setup with Makefile, CI pipeline, and Docker config
- **Safety hooks** - PreToolUse blocks dangerous commands; PostToolUse masks secrets in output

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for MCP servers)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- GitHub CLI (`gh`) for issue/PR workflows

## Quick Start

```bash
# Clone
git clone https://github.com/cooneycw/claude-power-pack.git
cd claude-power-pack

# Install dependencies
uv sync --extra dev

# Run quality checks
make verify

# Start MCP servers (requires .env with API keys)
make docker-up PROFILE=core            # Second Opinion + Nano Banana
make docker-up PROFILE="core browser"  # + Playwright

# Initialize in a target project
cd ~/Projects/my-project
/cpp:init
```

## Project Structure

```
claude-power-pack/
  .claude/commands/     Slash commands (/flow:*, /cicd:*, /security:*, etc.)
  .claude/hooks.json    Safety hooks (pre/post tool use)
  mcp-second-opinion/   Code review MCP server
  mcp-playwright-persistent/  Browser automation MCP server
  mcp-nano-banana/      Diagram + PowerPoint MCP server
  lib/creds/            Secrets management library
  lib/security/         Security scanning library
  lib/cicd/             CI/CD framework detection and generation
  lib/spec_bridge/      Spec-to-GitHub-issue sync
  docs/skills/          Topic-focused best practices (~3K tokens each)
  woodpecker/           Woodpecker CI server + agent deployment configs
  templates/            Makefile, workflow, and container templates
  scripts/              Shell utilities
  tests/                211 unit tests
  docker-compose.yml    MCP server orchestration
  .woodpecker.yml       CI pipeline (lint, test, typecheck, deploy)
  Makefile              Build interface for all operations
```

## Key Commands

| Category | Command | Description |
|----------|---------|-------------|
| Workflow | `/flow:auto 42` | Full issue lifecycle in one shot |
| Workflow | `/flow:start 42` | Create worktree for an issue |
| Workflow | `/flow:finish` | Lint, test, commit, push, create PR |
| Project | `/project:init myapp` | Scaffold a new project |
| Security | `/security:scan` | Full vulnerability scan |
| Secrets | `/secrets:list` | List managed credentials |
| CI/CD | `/cicd:init` | Detect framework, generate Makefile |
| Docs | `/documentation:c4` | Generate C4 architecture diagrams |
| Review | `/second-opinion:start` | Get code review from external LLMs |

## Docker Deployment

MCP servers run as Docker containers organized by profile:

```bash
make docker-up PROFILE=core       # second-opinion + nano-banana
make docker-up PROFILE="core browser"  # + playwright
make docker-ps                    # container status
make docker-down                  # stop all
```

API keys are read from a root `.env` file (gitignored). For production, use AWS Secrets Manager via `lib/creds`.

## CI/CD

Woodpecker CI runs on push/PR:
- **Quality gates:** lint (ruff), test (pytest), typecheck (mypy)
- **Docker builds:** Conditional per-server image builds when `mcp-*/` files change
- **Auto-deploy:** On push to main, changed MCP servers are rebuilt and restarted via the local agent

## License

MIT - see [LICENSE](LICENSE)
