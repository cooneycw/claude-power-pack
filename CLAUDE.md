# Claude Power Pack

## Core Directives

- **NEVER output API keys, passwords, connection strings, or `.env` file contents in responses.** The PostToolUse hook masks terminal output, but your response text is logged before masking applies.
- **Use `make` targets for all build/deploy/Docker operations.** Never run raw `docker compose`, `uv run ruff`, or `uv run pytest` directly. If a target is missing, add it to the Makefile.
- **Progressive disclosure:** Do NOT auto-load documentation. Read topic-specific files from `docs/skills/` only when the task requires it.
- **Python 3.11+, uv for dependencies.** Each component has its own `pyproject.toml`.
- **When fixing errors, fix BOTH the application code AND the CI/CD process** (Makefile, Dockerfile, docker-compose.yml). Never bypass quality gates.
- Before debugging manually, run `make lint` and `make test` to surface known issues.
- After any fix, verify through the full pipeline: `make verify`.
- Use `/dockers` to check container status, health, and project linkages.

## Project Map

Core components and their locations:

- `docs/skills/` — Topic-focused best practices (~3K tokens each). Load on demand.
- `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` — Complete guide (25K tokens). Load via `/load-best-practices`.
- `ISSUE_DRIVEN_DEVELOPMENT.md` — IDD methodology
- `PROGRESSIVE_DISCLOSURE_GUIDE.md` — Context optimization patterns
- `MCP_TOKEN_AUDIT_CHECKLIST.md` — Token efficiency checklist
- `.specify/` — Spec-Driven Development (specs, plans, tasks, templates)
- `mcp-second-opinion/` — Code review MCP server (port 8080)
- `mcp-playwright-persistent/` — Browser automation MCP server (port 8081, 29 tools)
- `mcp-nano-banana/` — Diagram generation + PowerPoint MCP server (port 8084)
- `extras/sequential-thinking/` — Optional: structured reasoning (stdio, npm)
- `lib/creds/` — Secrets management (dotenv/AWS SM, FastAPI UI, audit logging)
- `lib/security/` — Security scanning (native + external tools)
- `lib/cicd/` — CI/CD framework detection, Makefile generation, health/smoke checks
- `lib/spec_bridge/` — Spec-to-GitHub-issue sync
- `scripts/` — Shell utilities (prompt-context, worktree-remove, hooks)
- `templates/` — Makefile, workflow, container templates
- `docker-compose.yml` — MCP server orchestration (profiles: `core`, `browser`)
- `.woodpecker.yml` — Woodpecker CI pipeline (lint, test, typecheck, Docker builds)

## Environment Variables

- `CLAUDE_PROJECT` — Default project for `/project-next` from `~/Projects`. Set in `~/.bashrc`.

## Docker Deployment

Docker containers read API keys from a root `.env` file (gitignored) via `env_file` in docker-compose.yml. For production, use AWS Secrets Manager via `lib/creds`.

- **Profiles:** `core` (second-opinion + nano-banana), `browser` (playwright)
- **Start:** `make docker-up PROFILE=core`
- **All profiles:** `make docker-up PROFILE="core browser"`
- **Status/logs/stop:** `make docker-ps`, `make docker-logs`, `make docker-down`
- **MCP connections:** Defined in project `.mcp.json` pointing to `127.0.0.1:{port}/mcp` (streamable-http)
- **Woodpecker CI** runs on push/PR: lint, test, typecheck, conditional Docker builds

## Commands Reference

### Workflow
- `/flow:start` — Create worktree for an issue
- `/flow:check` — Run lint + test + security scan (no commit)
- `/flow:finish` — Quality gates, commit, push, create PR
- `/flow:deploy [target]` — Run make deploy + health/smoke checks
- `/flow:auto` — Full issue lifecycle in one shot
- `/flow:merge` — Merge PR, clean up worktree
- `/flow:sync` — Push WIP to remote for cross-machine pickup
- `/flow:cleanup` — Prune stale worktrees and branches
- `/flow:status` — Show active worktrees
- `/flow:doctor` — Diagnose workflow environment

### Project
- `/project:init <name>` — Full project scaffolding (zero to GitHub repo)
- `/project-next` — Full issue analysis and prioritization (~15-30K tokens)
- `/project-lite` — Quick project reference (~500-800 tokens)

### Spec-Driven Development
- `/spec:init` — Initialize `.specify/` structure
- `/spec:create NAME` — Create new feature specification
- `/spec:sync [NAME]` — Sync tasks.md to GitHub issues
- `/spec:status` — Show spec/issue alignment

### GitHub Issues
- `/github:issue-list` — List and search issues
- `/github:issue-create` — Create new issue
- `/github:issue-view` — View issue details
- `/github:issue-update` — Update existing issue
- `/github:issue-close` — Close issue with optional comment

### CI/CD
- `/cicd:init` — Detect framework, generate Makefile and cicd.yml
- `/cicd:check` — Validate Makefile against CPP standards
- `/cicd:health` — Run health checks (endpoints + processes)
- `/cicd:smoke` — Run smoke tests from cicd.yml
- `/cicd:pipeline` — Generate GitHub Actions workflows
- `/cicd:container` — Generate Dockerfile and docker-compose.yml
- `/cicd:infra-init` — Scaffold IaC directory (foundation/platform/app tiers)
- `/cicd:infra-discover` — Generate cloud resource discovery script for IaC import
- `/cicd:infra-pipeline` — Generate per-tier CI/CD pipelines with approval gates

### Security
- `/security:scan` — Full scan: native + external tools
- `/security:quick` — Fast scan: native only (zero deps)
- `/security:deep` — Deep scan: includes git history
- `/security:explain <ID>` — Explain a finding type

### Secrets
- `/secrets:get`, `/secrets:set`, `/secrets:delete`, `/secrets:list` — CRUD operations
- `/secrets:run -- CMD` — Run command with secrets injected as env vars
- `/secrets:validate` — Test credential configuration
- `/secrets:ui` — Launch web UI
- `/secrets:rotate KEY` — Rotate a secret

### Documentation
- `/documentation:pptx [topic]` — Guided PowerPoint creation with diagrams
- `/documentation:c4` — Generate C4 architecture diagrams (all 4 levels)

### Evaluation
- `/evaluate:issue` — 4-phase multi-model evaluation (divergence, reasoning, validation, spec output)

### Second Opinion
- `/second-opinion:start [file] [model] [depth]` — Quick code review via external LLMs
- `/second-opinion:models` — Interactive model/depth selection

### Other
- `/dockers` — Docker container status, health, project linkages
- `/cpp:init` — Interactive setup wizard (Tiers: Minimal, Standard, Full, CI/CD)
- `/cpp:status` — Check installation state
- `/cpp:update` — Pull latest, sync deps
- `/self-improvement:deployment` — Retrospective analysis after failed deploys
- `/happy-check` — Check happy-cli version (optional)

## Makefile Integration

Flow commands use Makefile targets as the canonical build interface:

- `/flow:check` and `/flow:finish` run `make lint` and `make test`
- `/flow:deploy` runs `make deploy` (or specified target) + post-deploy health/smoke
- `/flow:auto` runs `make deploy` after merge, `make update_docs` after implement
- `/flow:doctor` reports which standard targets are available
- Deploy metadata in `.claude/deploy.yaml` (optional `requires_confirmation: true`)
- Deploy history logged to `.claude/deploy.log`
- Starter template at `templates/Makefile.example`

## Security

- **PreToolUse hook** blocks dangerous commands (force push to main, `rm -rf /`, `DROP TABLE`, etc.)
- **PostToolUse hook** masks secrets in Bash/Read output (connection strings, API keys, env vars)
- **Hooks configured in** `.claude/hooks.json`
- `/flow:finish` and `/flow:deploy` run security quick scan as quality gates
- CRITICAL findings block gates; HIGH findings produce warnings
- Configure gating in `.claude/security.yml`

## On-Demand Documentation

Load topic-specific skills instead of the full guide (88-92% token savings):

- Context efficiency, session management, MCP optimization, skills patterns
- Hooks/automation, spec-driven dev, issue-driven dev, CLAUDE.md config
- Code quality, Python packaging, CI/CD verification, documentation/diagrams

**Commands:** `/load-best-practices` (full 25K guide), `/load-mcp-docs` (MCP server docs)

## Secrets Management

Tiered: dotenv-global (`~/.config/claude-power-pack/secrets/`) -> env-file -> AWS Secrets Manager. Features: project identity (git-based), bundle API, secret injection (`creds run`), FastAPI web UI, audit logging, IAM isolation, output masking. Configure in `.claude/secrets.yml`.

## Version

Current version: 5.0.0
