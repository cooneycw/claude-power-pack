# Claude Power Pack

**v7.2.0** - A productivity toolkit for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds workflow automation, MCP servers, security scanning, secrets management, and CI/CD integration.

## What It Does

- **Workflow commands** (`/flow:auto`, `/flow:start`, `/flow:eli5`, `/flow:finish`) - Issue-driven development with worktrees, a pre-implementation ELI5 plan/necessity approval gate, quality gates, automated PR lifecycle, and CI verification
- **MCP servers** extending Claude Code's capabilities:
  - **Second Opinion** (port 8080, containerized) - Multi-model code review via external LLMs (Gemini, OpenAI, Anthropic)
  - **Browser automation** - upstream `@playwright/mcp` server (npx/stdio, no container), registered by `/cpp:init`
- **PowerPoint generation** - Slide decks via the native Anthropic `pptx` skill (`npx skills add anthropics/skills@pptx`)
- **Security scanning** (`/security:scan`) - Native vulnerability detection with git history analysis
- **Secrets management** (`/secrets:*`) - Tiered credential storage (dotenv, env-file, AWS Secrets Manager) with audit logging and a web UI
- **CI/CD integration** (`/cicd:*`) - Framework detection, Makefile generation, health checks, and IaC scaffolding
- **Woodpecker CI** - Self-hosted pipeline with image security gates, isolated MCP runtime smoke tests, and programmatic status polling
- **Project scaffolding** (`/project:init`) - Zero-to-GitHub-repo setup with Makefile, CI pipeline, and Docker config
- **Skills ecosystem** - Discover, install, and manage agent skills from [skills.sh](https://skills.sh/) via native `npx skills` and the `/plugin` marketplace (the CPP `/skills:*` wrapper was retired in issue #437)
- **Secret-masking hook** - a PostToolUse hook masks secrets (connection strings, API keys, env vars) in Bash/Read output; destructive commands are handled by Claude Code's native git auto-blocking + OS sandbox

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

# Start MCP servers (local .env or CI env provides AWS credentials)
# local .env needs: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_TOKEN
make docker-secrets-check              # Validate AWS connectivity
make docker-up PROFILE=core            # Second Opinion
make docker-refresh PROFILE=core       # Rebuild, restart, wait for health

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
  lib/creds/            Secrets management library
  lib/security/         Security scanning library
  lib/cicd/             CI/CD framework detection and generation
  docs/skills/          Topic-focused best practices (~3K tokens each)
  woodpecker/           Woodpecker CI server + agent deployment configs
  templates/            Makefile, workflow, and container templates
  scripts/              Shell utilities
  tests/                595 unit tests
  docker-compose.yml    MCP server orchestration
  .woodpecker.yml       CI pipeline (lint, test, typecheck, image security gates, runtime smoke)
  Makefile              Build interface for all operations
```

## Key Commands

| Category | Command | Description |
|----------|---------|-------------|
| Workflow | `/flow:auto 42` | Full issue lifecycle in one shot |
| Workflow | `/flow:start 42` | Create worktree for an issue |
| Workflow | `/flow:eli5 42` | Plain-language intent + necessity verdict + plan approval gate |
| Workflow | `/flow:finish` | Lint, test, commit, push, create PR |
| Improve | `/self-improvement:retro` | Post-run friction retro: capture -> codify durable fixes (the grill-me cycle) |
| Project | `/project:init myapp` | Scaffold a new project |
| Security | `/security:scan` | Full vulnerability scan |
| Secrets | `/secrets:list` | List managed credentials |
| CI/CD | `/cicd:init` | Detect framework, generate Makefile |
| Docs | `/documentation:c4` | Generate C4 architecture diagrams |
| Browser | `/browser:session create gmail` | Named concurrent browser sessions (lease-desk pool) |
| Review | `/second-opinion:start` | Get code review from external LLMs |

## Docker Deployment

MCP servers run as Docker containers organized by profile:

```bash
make docker-up PROFILE=core       # second-opinion
make docker-refresh PROFILE=core  # transactional rebuild/restart with health gate
make docker-ps                    # container status
make docker-down                  # stop all
```

MCP containers fetch API keys at startup from AWS Secrets Manager via an `aws-secrets-agent` sidecar (Rust binary, port 2773). The sidecar is internal-only (compose network via `expose:`, never published to the host) and is the only container that receives AWS credentials. Local development can store only AWS credentials in the root `.env` file (gitignored), while CI/deploy can inject the same variables through the job environment. Application secrets are not stored on disk.

`mcp-second-opinion` uses `AWS_SECRET_NAME=codex_llm_apikeys`. That secret must include `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY` so the model catalog is available in the deployed container.

```bash
# Minimal .env (no application secrets):
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_TOKEN=my-ssrf-token   # must be unique; the preflight rejects empty or "default-token"
SECOND_OPINION_AWS_SECRET_NAME=codex_llm_apikeys

# Validate before first start:
make docker-secrets-check
```

App containers carry no AWS credentials; they reach the sidecar over the compose network with only the SSRF token. `make docker-up` refuses to create the sidecar when required AWS credential variables resolve empty or `AWS_TOKEN` is the insecure default (set `CPP_ALLOW_DEFAULT_TOKEN=1` for offline local dev only). `make deploy` is stricter: it always rejects `default-token`, requires explicit secret-name variables for secret-consuming profiles, snapshots the current image IDs as `:previous`, and restores them if the candidate stack fails `docker compose --wait`. For host-side debugging or a fully offline `.env` fallback, layer in `docker-compose.dev.yml` (binds the agent to `127.0.0.1`, restores `.env` for app containers, and sets `ALLOW_ENV_FALLBACK=true`). See `aws-secrets-agent/` and `docs/AWS_SECRETS_SIDECAR.md` for details.

## CI/CD

Woodpecker CI runs on every push and PR via a self-hosted agent:

- **Validate:** lint (ruff) + test (pytest) + typecheck (mypy) in a single consolidated step
- **Image security:** MCP image changes build the compose stack, run hadolint over every Dockerfile, policy-check rendered compose config, fail on fixed HIGH/CRITICAL CVEs, and write SPDX/CycloneDX SBOMs under `artifacts/sbom/`
- **Runtime smoke:** MCP stack changes run an isolated `docker compose` project with random host ports, verify HTTP health, then tear down containers and volumes
- **CI verification:** `flow:auto` polls the Woodpecker API after merge to confirm the pipeline passes before deploying
- **First-class Docker updates:** `cpp:update` detects Docker installs, runs `make docker-refresh PROFILE=core`, and fails if containers are unhealthy

Architecture: Woodpecker server on a dedicated VM, agent on the dev workstation, connected via gRPC over Tailscale. Web UI at `woodpecker.essent-ai.com` via Cloudflare tunnel.

## Changelog

### v7.2.0 (2026-06-28)

- **`/flow:eli5` + `/flow:auto` approval gate** (#398) - plain-language intent, necessity/staleness verdict, and a plan-approval pause between Analyze and Implement
- **Skill drift/orphan detection in `/cpp:update`** (#395) - curated-list-driven detection and guarded prune of retired/orphaned generated skills
- **Fix:** `drift-detect.sh` no longer reports false Docker/systemd "deployment model conflict" on Docker-only hosts - systemd unit presence now derives from `LoadState`, not `is-active` (#400)

### v7.1.0 (2026-06-07)

- **Skills ecosystem integration** - New `/skills:*` command family wrapping the `npx skills` CLI for discovering, installing, and managing agent skills from [skills.sh](https://skills.sh/)
- Quality vetting in `/skills:find` checks install counts, source reputation, and GitHub stars before recommending

### v6.0.0 (2026-05-31)

- **Breaking change: Docker-only MCP deployment** - Docker with local builds is now the only supported Tier 3 runtime
- **Legacy systemd migration** - `cpp:update` detects legacy MCP systemd units and guides teardown before Docker refresh
- **Status clarity** - `cpp:status` reports `Docker (local build)` and labels remaining systemd units as migration-required legacy state

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

- **Woodpecker CI pipeline** - Self-hosted CI with MCP image security gates
- **Runtime smoke tests** - CI brings the MCP stack up in an isolated compose project, checks service health, then tears it down
- **CI verification in flow:auto** - New Step 7/8 polls Woodpecker or GitHub Actions after merge, blocks deploy on failure
- **Consolidated pipeline** - Merged lint/test/typecheck into single validate step (eliminates 2x `uv sync`)
- **Health-based runtime checks** - `docker compose --wait` validates container healthchecks during smoke runs
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
