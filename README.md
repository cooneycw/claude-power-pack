# Claude Power Pack

**v5.2.0** - A productivity toolkit for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds workflow automation, MCP servers, security scanning, secrets management, and CI/CD integration.

## What It Does

- **Workflow commands** (`/flow:auto`, `/flow:start`, `/flow:finish`) - Issue-driven development with worktrees, quality gates, automated PR lifecycle, and CI verification
- **MCP servers** - Three containerized servers extending Claude Code's capabilities:
  - **Second Opinion** (port 8080) - Multi-model code review via external LLMs (Gemini, OpenAI, Anthropic)
  - **Playwright Persistent** (port 8081) - Browser automation with 29 tools
  - **Nano Banana** (port 8084) - Diagram generation and PowerPoint creation
- **Security scanning** (`/security:scan`) - Native vulnerability detection with git history analysis
- **Secrets management** (`/secrets:*`) - Tiered credential storage (dotenv, env-file, AWS Secrets Manager) with audit logging and a web UI
- **CI/CD integration** (`/cicd:*`) - Framework detection, Makefile generation, health checks, and IaC scaffolding
- **Woodpecker CI** - Self-hosted pipeline with automated MCP server deployment, health-based verification, and programmatic status polling
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

# Start MCP servers (requires .env with AWS credentials)
# .env needs: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_TOKEN
make docker-secrets-check              # Validate AWS connectivity
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
  aws-secrets-agent/    AWS Secrets Manager sidecar (Rust, port 2773)
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
  tests/                496 unit tests
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

MCP containers fetch API keys at startup from AWS Secrets Manager via an `aws-secrets-agent` sidecar (Rust binary, port 2773). Only AWS credentials are stored in the root `.env` file (gitignored) - no application secrets on disk.

```bash
# Minimal .env (no application secrets):
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_TOKEN=my-ssrf-token

# Validate before first start:
make docker-secrets-check
```

If the sidecar is unreachable or `AWS_SECRET_NAME` is not set on a container, it falls back to `env_file` variables for local development. See `aws-secrets-agent/` and `docs/AWS_SECRETS_SIDECAR.md` for details.

## CI/CD

Woodpecker CI runs on every push and PR via a self-hosted agent:

- **Validate:** lint (ruff) + test (pytest, 496 tests) + typecheck (mypy) in a single consolidated step
- **Docker builds:** Conditional per-server dry-run builds when `mcp-*/` files change
- **Auto-deploy:** On push to main, changed MCP servers are rebuilt and health-checked via `docker compose --wait`
- **Disk cleanup:** Dangling images pruned after every deploy
- **CI verification:** `flow:auto` polls the Woodpecker API after merge to confirm the pipeline passes before deploying

Architecture: Woodpecker server on a dedicated VM, agent on the dev workstation, connected via gRPC over Tailscale. Web UI at `woodpecker.essent-ai.com` via Cloudflare tunnel.

## Changelog

### v5.2.0 (2026-03-08)

- **C4 diagram QA framework** - `validate_diagram` MCP tool with density scoring, XSS sanitization, WCAG AA contrast checks
- **Multi-diagram C4 generation** - L3 for all containers, L4 for top 3 components per container
- **Density-aware splitting** - `split_diagram` MCP tool auto-splits large diagrams into summary + detail views
- **QA gating in skills** - c4 and pptx skills check warnings after every `generate_diagram`, retry on edge errors, split on overflow
- **Shared theme tokens** - `ThemeTokens` contract for consistent colors across all diagram types
- **c4-manifest.json** - Tracks all generated diagrams with parent-child relationships
- **index.html** - Hierarchical navigation page for all C4 diagrams
- **XSS fix** - HTML-escape all node labels in diagram output
- **WCAG AA fix** - All color palettes meet 4.5:1 minimum contrast ratio
- **496 tests** - Comprehensive test coverage for validation, density, splitting, contrast, and C4 integration

### v5.1.0 (2026-03-07)

- **Woodpecker CI pipeline** - Self-hosted CI with automated MCP server deployment
- **CI verification in flow:auto** - New Step 7/8 polls Woodpecker or GitHub Actions after merge, blocks deploy on failure
- **Consolidated pipeline** - Merged lint/test/typecheck into single validate step (eliminates 2x `uv sync`)
- **Health-based deploys** - `docker compose --wait` replaces `sleep 5`, uses container healthchecks
- **Disk cleanup** - `docker image prune -f` after every deploy
- **Extended CI polling** - flow:auto timeout increased from 5 to 10 minutes
- **Woodpecker v3 API fix** - Repo ID lookup for correct API path

### v5.0.2 (2026-02-27)

- Nano Banana: Base64 OOM guard, Docker path fallback, validation tightening
- SlideDefinition dataclass for PowerPoint generation
- MCP server drift detection in `/cpp:update`

### v5.0.1 (2026-02-26)

- PPTX QC validation, multi-framework support, AWS gating
- Em dash cleanup across all markdown and documentation

## License

MIT - see [LICENSE](LICENSE)
