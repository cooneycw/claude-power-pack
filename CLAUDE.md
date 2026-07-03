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
- **Use single dashes (-) not em dashes (-)** in all markdown, comments, and documentation. Never generate Unicode em dashes (U+2014) or en dashes (U+2013).

## Project Map

Core components and their locations:

- `docs/skills/` - Topic-focused best practices (~3K tokens each). Load on demand.
- `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` - Complete guide (25K tokens). Load via `/load-best-practices`.
- `ISSUE_DRIVEN_DEVELOPMENT.md` - IDD methodology
- `PROGRESSIVE_DISCLOSURE_GUIDE.md` - Context optimization patterns
- `MCP_TOKEN_AUDIT_CHECKLIST.md` - Token efficiency checklist
- `.specify/` - Spec-Driven Development (specs, plans, tasks, templates)
- `aws-secrets-agent/` - AWS Secrets Manager sidecar (Rust, port 2773). See `docs/AWS_SECRETS_SIDECAR.md`.
- `mcp-second-opinion/` - Code review MCP server (port 8080)
- Browser automation - upstream `@playwright/mcp` registered via npx/stdio by `/cpp:init` (no container; the CPP `mcp-playwright-persistent` fork was retired in #423)
- `extras/sequential-thinking/` - Optional: structured reasoning (stdio, npm)
- `lib/creds/` - Secrets management (dotenv/AWS SM, FastAPI UI, audit logging)
- `lib/security/` - Security scanning (native + external tools)
- `lib/cicd/` - CI/CD framework detection, Makefile generation, health/smoke checks, deterministic runner, deployment strategies, Pydantic v2 config validation
- `lib/cpp_memory/` - Common-memory client: fail-open Postgres ledger of *portable* CPP learnings/infra traps shared across the VM fleet (bucket-2-plus), plus a dedup/rejection ledger. Store provisioned by `scripts/memories-db-setup.sh`. Consult-not-push; see `/self-improvement:memory`.
- `scripts/` - Shell utilities (prompt-context, worktree-remove, hooks, drift-detect, skill-drift, mcp-drift, speckit-tasks-to-issues, playwright-desk lease-desk ledger, check-ignored-additions)
- `templates/` - Makefile, workflow, container templates
- `docker-compose.yml` - MCP server orchestration (profile: `core`)
- `.woodpecker.yml` - Woodpecker CI pipeline (lint, test, typecheck, image security gates, runtime smoke)

## Environment Variables

- `CLAUDE_PROJECT` - Default project for `/project-next` from `~/Projects`. Set in `~/.bashrc`.

## Docker Deployment

Docker with local builds is the only supported MCP runtime in 6.0.0. Legacy systemd and venv-only runtime paths are removed; run `/cpp:update` to migrate any existing systemd units before refreshing containers.

MCP containers fetch API keys at startup from AWS Secrets Manager via an `aws-secrets-agent` sidecar. Local development can store only AWS credentials in the root `.env` file (gitignored), while CI/deploy can inject the same variables through the job environment. No application secrets are stored on disk. If `AWS_SECRET_NAME` is not set, containers use `env_file` variables (local dev mode). If `AWS_SECRET_NAME` is set but the fetch or parse fails, containers **fail closed** - they exit non-zero and never start keyless (issue #347). Set `ALLOW_ENV_FALLBACK=true` (e.g. via `docker-compose.dev.yml`) to opt into env-file fallback for local development.

- **Secrets architecture:** `aws-secrets-agent` (Rust binary, port 2773) caches secrets in-memory (300s TTL) with SSRF token protection. The agent is internal-only (`expose:`, never host-published) and is the only container that receives AWS credentials; MCP containers use `fetch-secrets.sh` entrypoint to resolve keys with just the SSRF token. Use `docker-compose.dev.yml` (loopback publish + `.env` fallback + `ALLOW_ENV_FALLBACK`) for host-side debugging / offline local dev only.
- **Required AWS credential variables:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_TOKEN` (SSRF token; must be unique - preflight rejects empty/`default-token`, override with `CPP_ALLOW_DEFAULT_TOKEN=1` for offline dev), supplied by local `.env` or CI/deploy environment
- **AWS secrets used:** `codex_llm_apikeys` (second-opinion LLM keys: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), `essent-ai` (Woodpecker CI keys: `WOODPECKER_URL`, `WOODPECKER_API_TOKEN` - consumed by `/flow:auto`, `woodpecker/bootstrap-secrets.py`, and `scripts/setup-woodpecker-cli.sh`; also holds `CPP_MEMORIES_DSN`, the common-memory Postgres DSN used by `lib/cpp_memory` for fleet-wide federation - reference the store host by its Tailscale address)
- **Required IAM permissions:** `secretsmanager:GetSecretValue`, `secretsmanager:DescribeSecret` scoped to the named secret ARNs, plus `kms:Decrypt` (scoped via `kms:ViaService`) when the secrets use a customer-managed CMK
- **Validate setup:** `make docker-secrets-check` (checks AWS creds, verifies secrets exist)
- **Profiles:** `core` (second-opinion + secrets-agent). Browser automation is the upstream `@playwright/mcp` npx/stdio server (no container, no compose profile; see `/cpp:init`).
- **Start:** `make docker-up PROFILE=core`
- **Rebuild/restart/wait for health:** `make docker-refresh PROFILE=core` snapshots current image IDs as `:previous` and restores them if the candidate stack fails `--wait`
- **Status/logs/stop:** `make docker-ps`, `make docker-logs`, `make docker-down`
- **Liveness vs readiness:** each MCP server serves `/` (liveness: process is up) and `/readyz` (readiness: required secrets/config actually loaded). Compose healthchecks - the `docker compose up --wait` release gate - probe `/readyz`, so a live-but-keyless container (e.g. a failed secret fetch) is reported unhealthy and `--wait` fails instead of greenlighting it. The secret-bearing server (`mcp-second-opinion`) reports ready only once its provider keys load. CI/deploy without a live secrets-agent can inject keys via the LLM env passthroughs in `docker-compose.yml`; the agent overrides them at runtime.
- **Empty AWS credential guard:** `make docker-up` refuses to create `aws-secrets-agent` when `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` resolves empty. If a stale sidecar was already created with empty creds, fix env and force-recreate `aws-secrets-agent` plus secret-dependent MCP containers.
- **Deploy preflight:** `make deploy` runs `scripts/assert-prod-env.sh`; production deploys reject `default-token` even if local-dev opt-out is set, and require `SECOND_OPINION_AWS_SECRET_NAME` for `core` plus `WOODPECKER_CI_AWS_SECRET_NAME` for `cicd`.
- **MCP connections:** Defined in project `.mcp.json` pointing to `127.0.0.1:{port}/sse` (SSE transport)
- **Woodpecker CI** runs on push/PR: secret-scan (gitleaks), lint, test, typecheck, Dockerfile lint, compose policy checks, image builds, image CVE scans, SBOM generation, and isolated runtime smoke tests for MCP stack changes
- **Secret scanning:** `make secret-scan` runs gitleaks locally (native binary or Docker fallback). Config in `.gitleaks.toml` with allowlists for doc/test false positives
- **Runtime smoke:** CI uses a `cpp-smoke-$CI_PIPELINE_NUMBER` compose project with random host ports (driven by `scripts/runtime-smoke.sh`), validates service health, asserts the agent is reachable cross-container at `http://aws-secrets-agent:2773` (proving the `0.0.0.0` bind), exercises the client's real fetch/parse/export path via a hermetic fake agent (`scripts/fake-secrets-agent.py` + `docker-compose.smoke.yml`) with a non-empty `AWS_SECRET_NAME`, and drives a secret through the **REAL** `aws-secrets-agent` binary against a LocalStack Secrets Manager (real AWS SDK `GetSecretValue` via `AWS_ENDPOINT_URL`, no production credentials) so a consumer actually receives a genuinely-fetched secret (issue #377). In-container readiness probes are retried (up to 10x, 3s apart) so a transient post-`--wait` connection refusal does not fail the build; on genuine exhaustion the step dumps `docker compose ps` and the failing service's recent logs (issue #375). It runs `docker compose down -v` before exiting. CI must not deploy persistent containers or prune host images.
- **Image security gates:** CI runs hadolint over every Dockerfile, validates `docker compose config --quiet`, blocks rendered `:latest`, `default-token`, and host-published agent port regressions, then scans built images for fixed HIGH/CRITICAL CVEs and writes SPDX/CycloneDX SBOMs to `artifacts/sbom/`.
- **Bootstrap checks:** `make bootstrap-check` verifies admin-only prerequisites (IAM roles, secrets provisioning) before deploy. Configure in `.claude/bootstrap.yaml`. Runs as the first step in the deploy pipeline - blocks with remediation if unsatisfied.
- **Drift detection:** `make drift-check` compares host-installed artifacts against repo templates and treats remaining systemd MCP units as legacy migration findings. It also flags **orphaned Docker MCP servers** - a container, `mcp-<name>:*` image, or `claude`/`codex mcp` registration left behind after a server is removed from `docker-compose.yml` - by deriving the current service set from `docker compose config --services` and matching against the curated `.claude/deprecated-mcps.yaml` list of record (via `scripts/mcp-drift.py`). Detection is curated-list driven so a user's own custom MCP registration is never flagged; teardown is offered per-server, user-confirmed, and keeps a newest-image restore point unless prune-all is chosen (run `/cpp:update`, or `python3 scripts/mcp-drift.py --teardown <name>`). Run it manually when reconciling workstation-managed artifacts. See `docs/HOST_MANAGED_ARTIFACTS.md` for full inventory.
- **Reproducible builds:** Every base image and build tool (python, rust, debian, `uv`, gitleaks, woodpecker server/agent) is pinned by version tag plus `@sha256:` digest in the Dockerfiles, `.woodpecker.yml`, and infra compose files - never `:latest`. Deployable images are tagged with `CPP_IMAGE_TAG` (the short git SHA, set by the Makefile) instead of `:latest`, so each image traces to a commit and rollbacks have provenance. `renovate.json` rotates the pinned digests on a weekly schedule so pinning never freezes security updates.

## Commands Reference

### Workflow
- `/flow:start` - Create worktree for an issue
- `/flow:eli5 <issue>` - Plain-language intent + necessity/staleness verdict + plan approval gate (runs after analyze, before implement)
- `/flow:check` - Run lint + test + security scan (no commit)
- `/flow:finish` - Quality gates, commit, push, create PR
- `/flow:deploy [target]` - Run make deploy + health/smoke checks
- `/flow:auto` - Full issue lifecycle in one shot (ELI5 plan/necessity approval gate between analyze and implement; `--yes` to skip the pause)
- `/flow:merge` - Merge PR, clean up worktree
- `/flow:sync` - Push WIP to remote for cross-machine pickup
- `/flow:cleanup` - Prune stale worktrees and branches
- `/flow:status` - Show active worktrees
- `/flow:doctor` - Diagnose workflow environment

**Native worktrees (issue #440):** `/flow` rides Claude Code's built-in
worktrees. `/flow:start` and `/flow:auto` create and enter a worktree with the
`EnterWorktree` tool (checkout under `.claude/worktrees/<name>`, branched from
`origin/<default-branch>` under the default `worktree.baseRef: fresh`) instead of
shelling out to `git worktree add`; same-session cleanup uses `ExitWorktree`.
`.claude/worktrees/` is gitignored. CPP layers its issue-anchored gate policy on
top of these mechanics and does not delegate it: the `issue-<N>-<slug>` branch
name (enforced after `EnterWorktree`), the `/flow:eli5` necessity gate, the
quality gates, and merge/cleanup discipline are unchanged. Because native
`ExitWorktree` only removes worktrees created in the current session, cross-session
and cross-machine cleanup (`/flow:merge`, `/flow:cleanup`) keep `git worktree
remove` / `scripts/worktree-remove.sh` as the fallback.

### Project
- `/project:init <name>` - Full project scaffolding (zero to GitHub repo)
- `/project-next` - Full issue analysis and prioritization (~15-30K tokens)
- `/project-lite` - Quick project reference (~500-800 tokens)

`/project:init` delegates config scaffolding (CLAUDE.md, skills, hooks) to Claude
Code's native `/init` interview rather than hand-rolling a fixed template, then
runs `/claude-md:lint` to overlay CPP's CI/CD governance directives. CPP keeps the
zero-to-GitHub-repo orchestration native `/init` does not provide: directory +
framework scaffold, `git init` and repo create/push, Makefile/CI wiring
(`lib/cicd`), CPP toolkit install, and `.specify/` structure (epic #417 Phase A,
mirrors the `/security` #438 and hooks #439 defer-the-commodity-half moves).

### Spec-Driven Development
- `/spec:adopt` - **(supported)** Install the official GitHub spec-kit CLI and scaffold it into the project (`specify init --here --ai claude`); then author with the `/speckit-*` skills and ship with `/flow:auto`. Turn `tasks.md` into GitHub issues with `scripts/speckit-tasks-to-issues.sh` (gh-CLI, no github-mcp-server). Per-project, always latest upstream. The `specify` CLI installs on first `/spec:adopt` use, or up front via `/cpp:init` / `/cpp:update`.
- `/spec:help` - Overview of the spec-kit authoring path

**Spec-driven dev = official spec-kit plugin + `/flow:auto`.** CPP's home-grown pipeline (`/spec:create`, `/spec:sync`, `/spec:status`, `/spec:init`, backed by `lib/spec_bridge`) was **retired** in favor of upstream spec-kit (epic #417 Phase A, decision on #418). Legacy generated `spec-*` skills are recorded in `.claude/deprecated-skills.yaml` and pruned by `/cpp:update`.

### GitHub Issues
- `/github:issue-list` - List and search issues
- `/github:issue-create` - Create new issue
- `/github:issue-view` - View issue details
- `/github:issue-update` - Update existing issue
- `/github:issue-close` - Close issue with optional comment

**Scaffolding backend:** GitHub Issues (driven by the `flow-auto` skillset) is the only supported scaffolding/issue backend. Wiki.js and Plane are out of scope and are not part of CPP. Retired skill families are recorded in `.claude/deprecated-skills.yaml`; the legacy `wiki-*` skills installed by older CPP versions are pruned via `/cpp:update` (see issue #395).

### CI/CD
- `/cicd:init` - Detect framework, generate Makefile and cicd.yml
- `/cicd:check` - Validate Makefile against CPP standards
- `/cicd:health` - Run health checks (endpoints + processes)
- `/cicd:smoke` - Run smoke tests from cicd.yml
- `/cicd:verify` - Verify a deployment against a pre-deploy baseline (proceed/review/rollback)
- `/cicd:pipeline` - Generate CI/CD workflows: GitHub Actions, or self-hosted Woodpecker via `pipeline.provider` (consults cicd_tasks.yml manifest if present)
- `/cicd:woodpecker` - Generate a hardened self-hosted Woodpecker pipeline (opt-in secret-scan + image-security + runtime-smoke stages) and scaffold the server/agent from `templates/woodpecker/`; see `docs/skills/woodpecker-ci.md`
- `/cicd:container` - Generate Dockerfile and docker-compose.yml
- `/cicd:infra-init` - Scaffold IaC directory (foundation/platform/app tiers)
- `/cicd:infra-discover` - Generate cloud resource discovery script for IaC import
- `/cicd:infra-pipeline` - Generate per-tier CI/CD pipelines with approval gates
- `python -m lib.cicd validate` - Validate .claude/cicd.yml with fix suggestions (Pydantic v2)
- `python -m lib.cicd validate --schema` - Generate JSON Schema for IDE autocompletion
- `python -m lib.cicd run --plan <name>` - Execute CI/CD plan deterministically (finish, check, deploy)
- `python -m lib.cicd verify --baseline` - Capture pre-deploy health/smoke baseline
- `python -m lib.cicd verify` - Verify post-deploy against baseline (exit 1 = ROLLBACK)
- `python -m lib.cicd.bootstrap check` - Check admin-only bootstrap dependencies (config: `.claude/bootstrap.yaml`)

### Codex Orchestration
- `/codex:auto <ISSUE>` - Full issue lifecycle delegated to Codex CLI (worktree, implement, review, quality gates, PR)
- `/codex:exec <PROMPT>` - One-shot Codex execution in current directory with JSONL monitoring
- `/codex:ask <QUESTION>` - Delegate a read-only question to Codex and relay its answer (read-only by default; network opt-in on explicit request)
- `/codex:status` - Check Codex CLI installation, config, and readiness
- `/codex:help` - Codex commands overview

### Security
- `/security:scan` - Full scan: native + external tools
- `/security:quick` - Fast scan: native only (zero deps)
- `/security:deep` - Deep scan: includes git history
- `/security:explain <ID>` - Explain a finding type

### Secrets
- `/secrets:get`, `/secrets:set`, `/secrets:delete`, `/secrets:list` - CRUD operations
- `/secrets:run -- CMD` - Run command with secrets injected as env vars
- `/secrets:validate` - Test credential configuration
- `/secrets:ui` - Launch web UI
- `/secrets:rotate KEY` - Rotate a secret

### Documentation
- `/documentation:pptx [topic]` - Guided PowerPoint creation with diagrams (QA gating; screenshots via the upstream `@playwright/mcp` server)
- `/documentation:c4` - Generate C4 architecture diagrams as GitHub-renderable Mermaid via `scripts/c4-mermaid.py` (all 4 levels, per-container L3, per-component L4; flowchart L1-L3 + classDiagram L4; edge-validity QA gate, density-split hints, `index.md` + manifest)

### Evaluation
- `/evaluate:issue` - 4-phase multi-model evaluation (divergence, reasoning, validation, spec output)

### Second Opinion
- `/second-opinion:start [file] [model] [depth]` - Quick code review via external LLMs
- `/second-opinion:models` - Interactive model/depth selection

### QA
- `/qa:test` - Automated web testing via the upstream `@playwright/mcp` server (single session)

### Browser Sessions
- `/browser:session <verb> [name]` - Named **concurrent** browser sessions over upstream `@playwright/mcp` via a static "lease-desk" pool (create/resume/save/close/list/cleanup/pool). Recovers the one feature upstream lacks (microsoft/playwright-mcp#1530) with no fork. Opt-in pool registered via `/cpp:init` (Full tier -> browser pool); ledger in `scripts/playwright-desk.py`. See `docs/skills/browser-session-wrapper.md`.
- `/browser:help` - Browser session commands overview

### CLAUDE.md Management
- `/claude-md:lint` - Lint CLAUDE.md for missing CI/CD, Docker, and troubleshooting directives

### Skills
The `/skills:*` wrapper was retired (issue #437) - it is fully absorbed
by the native Claude Code ecosystem. Use these instead:
- `npx skills find|add|list|update <...>` - Discover/install/manage skills from [skills.sh](https://skills.sh/)
- `/plugin` - Browse and install from the plugin marketplace
- Auto-loading `.claude/skills` + `/reload-skills` - Project-local skills, no wrapper needed

### Other
- `/dockers` - Docker container status, health, project linkages
- `/cpp:init` - Interactive setup wizard (Tiers: Minimal, Standard, Full, CI/CD, Codex); optionally installs the spec-kit CLI (`specify`, the engine behind `/spec:adopt`)
- `/cpp:status` - Check installation state
- `/cpp:update` - Pull latest, sync deps, migrate legacy systemd units if present, refresh Docker local-build runtime, tear down orphaned Docker MCP infra via the curated `.claude/deprecated-mcps.yaml` (Step 6c/7, user-confirmed), prune retired/orphaned generated skills via the curated `.claude/deprecated-skills.yaml` (Step 7.5, user-confirmed), then offer to merge new flow allowlist rules from `templates/claude-settings-permissions.json` into `~/.claude/settings.json` (Step 7.6, user-confirmed); also refreshes the optional spec-kit CLI (`specify`) if installed (Step 4.6)
- `/self-improvement:retro` - Post-run friction retro (the grill-me cycle): always-on capture (`scripts/friction-log.sh` -> `.claude/friction.jsonl`, woven into `/flow:auto` + `/flow:merge`) then classify -> dedup -> propose -> confirm -> codify durable fixes; local ledger `.claude/learnings.md`, portable knowledge delegates to `/self-improvement:memory` (#433)
- `/self-improvement:deployment` - Retrospective analysis after failed deploys
- `/self-improvement:memory` - Populate the shared common-memory ledger with portable friction-knowledge (bucket-2-plus); consult-not-push, fail-open
- `/happy-check` - Check happy-cli version (optional)

## Makefile Integration

Flow commands use Makefile targets as the canonical build interface:

- `/flow:check` and `/flow:finish` use `python -m lib.cicd run --plan finish` (deterministic runner) with fallback to `make lint` / `make test`
- `/flow:deploy` uses `python -m lib.cicd run --plan deploy` (deterministic runner) with fallback to `make deploy` + post-deploy health/smoke
- `/flow:auto` runs `make update_docs` after implement, verifies CI after merge, then `make deploy`
- `/flow:doctor` reports which standard targets are available
- Deploy metadata in `.claude/deploy.yaml` (optional, created manually when needed)
- Deploy history logged to `.claude/deploy.log`
- Starter template at `templates/Makefile.example`

## Security

Security is split into two complementary halves. **Semantic** code-vulnerability
review - SQL injection, XSS, broken authorization, insecure credential handling -
is handled by Claude Code's native **`/security-review`** command and its GitHub
Action; CPP defers to it and does not duplicate it. CPP's `/security:*` commands
and `lib/security` own the **deterministic** complement: secret scanning
(gitleaks + native patterns), git-history secret scanning, dependency CVE audits
(`pip-audit`, `npm audit`), and the blocking gate. See `lib/security/README.md`.

- **Destructive commands** (force push to main, `rm -rf /`, disk formatting, etc.) are blocked by Claude Code's native destructive-git auto-blocking and OS sandbox - the custom PreToolUse dangerous-command hook was retired (issue #439) as redundant.
- **PostToolUse hook** masks secrets in Bash/Read output (connection strings, API keys, env vars). Retained because native tooling blocks credential *reads* but does not *mask* secrets that surface in output.
- **Hooks configured in** `.claude/hooks.json` (SessionStart + PostToolUse)
- `/flow:finish` and `/flow:deploy` run the deterministic security scan (`lib/security`) as a quality gate
- CRITICAL findings block gates; HIGH findings produce warnings
- Configure gating in `.claude/security.yml` (optional, created by `/security:scan` when needed)
- For **semantic** code review (SQLi/XSS/authz/insecure handling), run native `/security-review` - not a CPP command
- **User-level flow allowlist** (`templates/claude-settings-permissions.json`) auto-approves the read-only git/gh plumbing that `/flow:*` runs; shipping actions (`git push`, `gh pr create`) and `cat` are deliberately excluded so gates and secret-read prompts stay intact. Merged via `/cpp:init` or `/cpp:update` Step 7.6; checked by `/flow:doctor`. Rationale: `templates/claude-settings-permissions.md`

## On-Demand Documentation

Load topic-specific skills instead of the full guide (88-92% token savings):

- Context efficiency, session management, MCP optimization, skills patterns
- Hooks/automation, spec-driven dev, issue-driven dev, CLAUDE.md config
- Code quality, Python packaging, CI/CD verification, documentation/diagrams

**Commands:** `/load-best-practices` (full 25K guide), `/load-mcp-docs` (MCP server docs)

## Secrets Management

Tiered: dotenv-global (`~/.config/claude-power-pack/secrets/`) -> env-file -> AWS Secrets Manager. Features: project identity (git-based), bundle API, secret injection (`creds run`), FastAPI web UI, audit logging, IAM isolation, output masking. Configure in `.claude/secrets.yml` (optional, created manually when needed).

## Version

Current version: 7.3.0
