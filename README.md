# Claude Power Pack

**v7.3.0** - A productivity toolkit for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds workflow automation, MCP servers, security scanning, secrets management, and CI/CD integration.

## What It Does

- **Workflow commands** (`/flow:auto`, `/flow:start`, `/flow:eli5`, `/flow:finish`) - Issue-driven development with worktrees, a pre-implementation ELI5 plan/necessity approval gate, quality gates, automated PR lifecycle, and CI verification. The necessity gate also ships standalone as [eli5-gate](https://github.com/cooneycw/eli5-gate) - installable without CPP via `/plugin marketplace add cooneycw/eli5-gate` or `npx skills add cooneycw/eli5-gate`; CPP vendors its canonical core (file gate improvements there)
- **MCP servers** extending Claude Code's capabilities:
  - **Second Opinion** - Multi-model code review via external LLMs (Gemini, OpenAI, Anthropic), served by the external `cooneycw/mcp-second-opinion` repo and wired in through the root `.mcp.json` (streamable-http)
  - **Browser automation** - upstream `@playwright/mcp` server (npx/stdio, no container), registered by `/cpp:init`
- **PowerPoint generation** - Slide decks via the native Anthropic `pptx` skill (`npx skills add anthropics/skills@pptx`)
- **Security scanning** (`/security:scan`) - Native vulnerability detection with git history analysis
- **Secrets management** (`/secrets:*`) - Tiered credential storage (dotenv, env-file, AWS Secrets Manager) with audit logging and a web UI
- **CI/CD integration** (`/cicd:*`) - Framework detection, Makefile generation, health checks, and IaC scaffolding
- **Woodpecker CI** - Self-hosted pipeline (secret-scan, lint, test, typecheck, Dockerfile lint) with programmatic status polling
- **Project scaffolding** (`/project:init`) - Zero-to-GitHub-repo setup with Makefile, CI pipeline, and Docker config
- **Skills ecosystem** - Discover, install, and manage agent skills from [skills.sh](https://skills.sh/) via native `npx skills` and the `/plugin` marketplace (the CPP `/skills:*` wrapper was retired in issue #437)
- **Secret-masking hook** - a PostToolUse hook masks secrets (connection strings, API keys, env vars) in Bash/Read output; bundled inside the `secrets` plugin (#479), so plugin installs get masking with no host script setup; destructive commands are handled by Claude Code's native git auto-blocking + OS sandbox

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (optional - only to run the external second-opinion server locally, or as the gitleaks fallback for `make secret-scan`)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- GitHub CLI (`gh`) for issue/PR workflows

## Install

CPP ships as a **plugin marketplace** (ADR [0001](docs/decisions/0001-plugin-marketplace-packaging.md), epic #417 Phase B). The command/skill/hook surface installs through Claude Code's `/plugin`, so there is nothing to clone and no symlink installer to run:

```
# In Claude Code, add the marketplace once:
/plugin marketplace add cooneycw/claude-power-pack

# Then install only the families you want (each is an independent plugin):
/plugin install flow@cpp
/plugin install cicd@cpp
/plugin install secrets@cpp
# ... browser, claude-md, codex, documentation, evaluate, github, project,
#     qa, second-opinion, security, self-improvement (15 in all), plus the
#     help-only cpp plugin.
```

`/plugin` handles versioning and updates for the installed surfaces. The `secrets` plugin bundles the PostToolUse secret-masking hook, so a plugin-only install gets masking with no host setup. **If you installed `flow`, run `/flow:repair` once**: its commands call a family of helper scripts, and while the plugin bundles them, they have to be placed at `~/.claude/scripts/` - the stable path the shipped permission allowlist matches - before `/flow:start` and `/flow:auto` will run (issue #590). Re-run it after a plugin upgrade; `/flow:doctor` reports when the installed copies have gone stale. The `second-opinion` plugin ships the review *commands* only and deliberately does NOT auto-register an MCP server (the external server is opt-in and not running on a fresh box, so auto-registration would surface as "1 error during load"); register it yourself once the server is up (see below).

### Non-plugin setup (the fallback `/plugin` cannot cover)

A plugin install delivers commands, skills, and hooks - but not the out-of-band infrastructure some families reach, and not an auto-registered MCP server. Run `/cpp:init` in a target project for those steps (it is now the non-plugin infra installer, not the primary way to get commands):

- **External Second Opinion server** - the multi-model review server lives in its own repo ([cooneycw/mcp-second-opinion](https://github.com/cooneycw/mcp-second-opinion)). The `second-opinion` plugin ships the review commands only and does NOT auto-register the server; start the external server, then register it with `claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user` (use your Tailscale URL for a remote host).
- **Browser automation** - registers the upstream `@playwright/mcp` npx/stdio server (no container).
- **Secrets provisioning** - AWS Secrets Manager access for Woodpecker CI keys (`essent-ai`) and the `CPP_MEMORIES_DSN` common-memory DSN; fetched directly via the AWS SDK/CLI.
- **Bootstrap prerequisites** - `jq`, and the optional spec-kit CLI (`specify`, the engine behind `/spec:adopt`).
- **Permission census hook + flow allowlist** - registers the observe-only PermissionRequest census hook and merges the read-only `/flow:*` allowlist - including the audited flow helper-script rules that make `/flow:auto` Phase 1 prompt-free (issue #581) - into `~/.claude/settings.json` (both user-confirmed).

`/cpp:update` refreshes those same non-plugin artifacts. See [`docs/HOST_MANAGED_ARTIFACTS.md`](docs/HOST_MANAGED_ARTIFACTS.md) for the full inventory.

### Developing CPP itself

To work on CPP (not just use it), clone and run the quality gates:

```bash
git clone https://github.com/cooneycw/claude-power-pack.git
cd claude-power-pack
uv sync --extra dev
make verify
```

`.claude/commands/<family>/*.md` is the permanent source of truth; the `plugins/` copies are byte-identical artifacts regenerated by `scripts/plugin-sync.sh --write` and guarded by `--check`. The same source also feeds the Codex harness: `scripts/codex-skill-sync.py` emits per-command Codex skills under `codex/skills/` (`make codex-skills`, issue #555), guarded by an explicit `codex-skills-check` CI step. The older flat `codex/prompts/` surface it replaced was retired at the #556 cutover.

## Project Structure

```
claude-power-pack/
  .claude/commands/     Slash commands (/flow:*, /cicd:*, /security:*, etc.)
  .claude/hooks.json    Safety hooks (pre/post tool use)
  .mcp.json             Client pointer for the external second-opinion server
  .claude-plugin/       Plugin-marketplace manifest (marketplace name: cpp)
  plugins/              Per-family plugins (15): /plugin install <family>@cpp (#477/#478, ADR 0001)
  codex/skills/         Generated Codex SKILL.md skills, second harness surface (#555)
  codex/cpp-memory.md   Curated Codex /cpp-memory prompt (#433; flat codex/prompts/ retired #556)
  lib/creds/            Secrets management library
  lib/security/         Security scanning library
  lib/cicd/             CI/CD framework detection and generation
  docs/skills/          Topic-focused best practices (~3K tokens each)
  woodpecker/           Woodpecker CI server + agent deployment configs
  templates/            Makefile, workflow, and container templates
  scripts/              Shell utilities
  tests/                Unit tests
  .woodpecker.yml       CI pipeline (secret-scan, lint, test, typecheck, Dockerfile lint)
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

## MCP Servers

CPP ships no container runtime (retired in #469). The `/second-opinion:*` and `/evaluate:*` commands consume an **external** second-opinion server that runs from its own repo:

- Server repo: https://github.com/cooneycw/mcp-second-opinion (server + the AWS Secrets Manager Agent sidecar build recipe + a standalone docker-compose)
- CPP ships a root `.mcp.json` registering `second-opinion` as a streamable-http client at `http://127.0.0.1:8080/mcp`. Start the external server, then edit that URL (or register it at user scope) to point at wherever it runs - localhost or a Tailscale host:

```bash
claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user
```

Browser automation uses the upstream `@playwright/mcp` npx/stdio server (registered by `/cpp:init`). CPP stores no application secrets on disk and runs no secrets sidecar; the remaining AWS Secrets Manager consumers (`essent-ai` for Woodpecker CI keys and the `CPP_MEMORIES_DSN` common-memory DSN) fetch directly via the AWS SDK/CLI.

## CI/CD

Woodpecker CI runs on every push and PR via a self-hosted agent:

- **Secret scan:** gitleaks over the tree before anything else runs
- **Validate:** lint (ruff) + test (pytest) + typecheck (mypy) in a single consolidated step
- **Dockerfile lint:** hadolint over any remaining Dockerfile
- **CI verification:** `flow:auto` polls the Woodpecker API after merge to confirm the pipeline passes

The image-build, CVE-scan, SBOM, compose-policy, and runtime-smoke stages were retired with CPP's Docker MCP runtime in #469.

Architecture: Woodpecker server on a dedicated VM, agent on the dev workstation, connected via gRPC over Tailscale. Web UI at `woodpecker.essent-ai.com` via Cloudflare tunnel.

## Changelog

### v7.3.0 (2026-07-04)

- **Plugin-marketplace distribution + install-path cutover** (epic #417 Phase B, ADR 0001) - CPP now installs through Claude Code's `/plugin`: `/plugin marketplace add cooneycw/claude-power-pack` then `/plugin install <family>@cpp` (15 per-family plugins). The dual command/skill surface, the `~/.claude/skills` global mirror, `flow-skill-sync.py`, `skill-drift.py`, and the symlink-installer paths were retired (#477/#478/#479/#480). `/cpp:init` / `/cpp:update` remain the installer for the non-plugin infra a plugin cannot cover (external MCP server pointer, secrets, bootstrap prereqs, permission-census hook, flow allowlist).
- **Docker MCP runtime retired** (#469, #423) - Second Opinion moved to its own external repo ([cooneycw/mcp-second-opinion](https://github.com/cooneycw/mcp-second-opinion)) consumed via a `.mcp.json` client pointer; browser automation moved to the upstream `@playwright/mcp` npx server. CPP ships no containers and `make deploy` is an informative no-op.
- **`/flow:eli5` necessity gate extracted** to the standalone [eli5-gate](https://github.com/cooneycw/eli5-gate) plugin (#443); CPP vendors its canonical core with a drift check.

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
