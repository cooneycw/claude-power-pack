# Claude Power Pack

## Core Directives

- **NEVER output API keys, passwords, connection strings, or `.env` file contents in responses.** The PostToolUse hook masks terminal output, but your response text is logged before masking applies.
- **Use `make` targets for build/test/deploy operations.** Never run raw `uv run ruff` or `uv run pytest` directly. If a target is missing, add it to the Makefile.
- **Progressive disclosure:** Do NOT auto-load documentation. Read topic-specific files from `docs/skills/` only when the task requires it.
- **Python 3.11+, uv for dependencies.** Each component has its own `pyproject.toml`.
- **When fixing errors, fix BOTH the application code AND the CI/CD process** (Makefile, Dockerfile, `.woodpecker.yml`). Never bypass quality gates.
- Before debugging manually, run `make lint` and `make test` to surface known issues.
- **A test that shells out to a real binary (`git`, `docker`, `gitleaks`) MUST guard with `@pytest.mark.skipif(shutil.which("<tool>") is None, ...)`.** The Woodpecker `validate` container (uv:python3.11-slim) ships none of them, so an unguarded test errors the suite and turns CI red even though it passes locally (recurred #451, #489).
- After any fix, verify through the full pipeline: `make verify`.
- Use `/dockers` to check container status, health, and project linkages.
- **Use single dashes (-) not em dashes (-)** in all markdown, comments, and documentation. Never generate Unicode em dashes (U+2014) or en dashes (U+2013).
- **One inventory item per line in CLAUDE.md.** When adding to an inventory entry (the `scripts/` list, component feature lists, CI behavior lists), add a new sub-bullet - never append to an existing line. Git merges at line granularity, so packed single-line lists make every concurrent PR that touches them a manual merge conflict (#501).

## Project Map

Core components and their locations:

- `docs/skills/` - Topic-focused best practices (~3K tokens each). Load on demand.
- `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` - Complete guide (25K tokens). Load via `/load-best-practices`.
- `ISSUE_DRIVEN_DEVELOPMENT.md` - IDD methodology
- `PROGRESSIVE_DISCLOSURE_GUIDE.md` - Context optimization patterns
- `MCP_TOKEN_AUDIT_CHECKLIST.md` - Token efficiency checklist
- `.specify/` - Spec-Driven Development (specs, plans, tasks, templates)
- `.mcp.json` - Client pointer for the external `second-opinion` MCP server (streamable-http `127.0.0.1:8080/mcp`). Run the server from its own repo (https://github.com/cooneycw/mcp-second-opinion); CPP's `mcp-second-opinion` container + `aws-secrets-agent` sidecar (and the whole Docker MCP runtime) were retired in #469.
- Browser automation - upstream `@playwright/mcp` registered via npx/stdio by `/cpp:init` (no container; the CPP `mcp-playwright-persistent` fork was retired in #423)
- `extras/sequential-thinking/` - Optional: structured reasoning (stdio, npm)
- `lib/creds/` - Secrets management (dotenv/AWS SM, FastAPI UI, audit logging)
- `lib/security/` - Security scanning (native + external tools)
- `lib/cicd/` - CI/CD framework detection, Makefile generation, health/smoke checks, deterministic runner, deployment strategies, Pydantic v2 config validation
- `lib/cpp_memory/` - Common-memory client: a **pluggable** fail-open friction-knowledge ledger (issue #472) with three `/cpp:init`-selectable backends behind one `StoreBackend` interface:
  - `md` - best-effort local, no federation; subsumes `.claude/learnings.md`
  - `local-pg` - full SQL dedup, single box, `lib/cpp_memory/docker-compose.yml`
  - `remote-pg` - full dedup, fleet-federated Postgres, `scripts/memories-db-setup.sh`
  - Backend chosen via `CPP_MEMORIES_BACKEND` / step 8d; **federation is a surfaced per-tier property** (only remote-pg shares across VMs)
  - Holds *portable* CPP learnings/infra traps (bucket-2-plus) plus a dedup/rejection ledger and a learnings->GitHub-issue bridge (`--emit-issue-candidate` / `link-issue`, #463)
  - Sightings carry a `harness` tag (`claude`|`codex`) for multi-harness attribution and a `sightings_by_harness` query split (#557); the write/read contract codex-power-pack targets is `docs/contracts/friction-ledger-shared-store.md`
  - Consult-not-push; see `/self-improvement:memory`
- `scripts/` - Shell utilities, one per sub-bullet (add new scripts as their own line, #501):
  - prompt-context
  - worktree-remove
  - gh-pr-merge - layout-aware PR squash-merge used by `/flow:auto` + `/flow:merge`; polls mergeability to wait out a transient `UNKNOWN` right after push (#485); bounded refetch+retry when the squash fails on `Base branch was modified` (sibling merge race, #502); opt-in `--admin` flag plus a single admin-gated auto-retry when a squash is rejected by branch protection on an owner merge (#517)
  - flow-stale-check - advisory early stale-base detector for `/flow:auto` Step 4/6 + `/flow:finish` (#473)
  - flow-worktree-guard - advisory leaked-edit detector: warns when a `/flow:auto` edit landed in the MAIN tree instead of the worktree (#486)
  - flow-start-resolve - deterministic `/flow` Step-1 resolver + `--verify` gate (#581): target-repo resolution (#578), issue fetch + state check, issue-anchored branch derivation, existing-work triage (`current-branch|fresh|resume|remote-pickup|cross-repo`), wraps the #503 live-driver guard + shipped-PR hazard, performs git-lane worktree creation (honoring `FLOW_WORKTREE_BASE`, #584), and emits a `key=value` contract - extracts the compound Step-1 bash the permission matcher could never auto-allow
  - flow-live-driver-guard - advisory concurrent-session guard (#503): warns when a worktree's dirty files were modified within the freshness window, the signature of another live session mid-implementation; wrapped by flow-start-resolve on the resume lane
  - hooks
  - drift-detect
  - mcp-drift
  - plugin-sync - byte-identical drift guard keeping every packaged family plugin in sync with its command source (#477/#478) plus per-family extra artifacts such as the secrets masking-hook script (#479); the B1 plugin-flow-sync shim was retired in B4 (#480)
  - codex-skill-sync - single-source -> per-harness SKILL.md generator (#555, CxPP epic cooneycw/codex-power-pack#64 story B1): emits checked-in per-command Codex skill dirs under `codex/skills/<family>-<cmd>/` (frontmatter name/description with front-loaded trigger words, Codex harness-adaptations block for detected Claude-only constructs, long bodies split to `reference.md`, referenced helper scripts bundled byte-identical); `--check` drift gate (pinned by tests/test_codex_skill_sync.py AND an explicit `codex-skills-check` step in `.woodpecker.yml`, #556), `--write` regen, `--install` copies to `~/.codex/skills/`; editing any bundled `scripts/*` requires a `--write` re-run. Superseded the deprecated flat `codex/prompts/` surface + its `codex-prompt-sync.py` generator, both retired at the #556 cutover
  - speckit-tasks-to-issues
  - playwright-desk - lease-desk ledger
  - check-ignored-additions - advisory guard warning when a blanket-ignore rule silently swallowed a file the repo should track; skips a short allow-list of files git-ignored by design (env-only `.claude/` runtime state such as `settings.local.json`/`friction.jsonl`) so it never cries wolf on them (#504)
  - sandbox-phase1-trial - ADR 0002 Phase 1 empirical trial harness (#548): runs the E1-E6 sandbox exit-bar checks in a throwaway, project-scoped trial (nested `claude -p` write-containment probes + a `bwrap` ro-bind primitive); never touches `~/.claude/settings.json`. Historical record only: the sandbox epic (#541) was abandoned (#553, ADR 0002 Rejected) after live enablement broke bash on the bwrap/symlink interaction
- `templates/` - Makefile, workflow, container templates
- `.claude-plugin/marketplace.json` - Plugin-marketplace manifest (marketplace name `cpp`) listing CPP's per-family plugins. Install path: `/plugin marketplace add cooneycw/claude-power-pack` then `/plugin install <family>@cpp` (ADR 0001, epic #417 Phase B).
- `plugins/` - Per-family Claude Code plugins. Phase B2 (#478) packages every surviving family (15 plugins, `browser` through `self-improvement`): byte-identical copies of `.claude/commands/<family>/*.md` (the single source of truth, ADR 0001 section 5), kept honest by `scripts/plugin-sync.sh --check` and regenerated with `--write` after any command edit. Phase B3 (#479) adds bundled hooks + MCP pointers: `secrets` ships the PostToolUse masking hook (plugin-local script via `${CLAUDE_PLUGIN_ROOT}`) and `second-opinion` ships its `.mcp.json` client pointer (matches the repo-root one). The `cpp` plugin is help/meta-only (the init/update/status installer stays repo-local). Phase B4 (#480) proved parity and retired the dual surface: the global-skill mirror, `flow-skill-sync.py`, `skill-drift.py`, and `.claude/deprecated-skills.yaml` are gone. Phase B5 (#481) cut the docs over to the `/plugin` install path (`/plugin marketplace add cooneycw/claude-power-pack` then `/plugin install <family>@cpp`); `/cpp:init` / `/cpp:update` remain only for the non-plugin infra a plugin cannot deliver.
- `codex/skills/` - Codex SKILL.md skills, the second harness surface (issue #555, companion to codex-power-pack epic cooneycw/codex-power-pack#64): generated `<family>-<cmd>/` skill dirs emitted from the same `.claude/commands/<family>/` single source by `scripts/codex-skill-sync.py`; codex-power-pack vendors this source (pull model, issue #556 / codex-power-pack#75) rather than receiving a push, and CPP's own currency is guarded by the explicit `codex-skills-check` step in `.woodpecker.yml`. Regenerate with `make codex-skills` after any command or referenced-script edit; `make codex-init` installs to `~/.codex/skills/`. Hand-curated skill dirs (no GENERATED marker) are never touched.
- `codex/cpp-memory.md` - Hand-curated Codex `/cpp-memory` prompt (#433) for the common-memory harness, installed to `~/.codex/prompts/cpp-memory.md` by `scripts/install-memory-harness.sh`. Relocated here when the deprecated generated `codex/prompts/` flat surface (#446) was retired at the #556 cutover (superseded by `codex/skills/`, #555).
- `.woodpecker.yml` - Woodpecker CI pipeline (secret-scan, lint, test, typecheck, Dockerfile lint)

## Environment Variables

- `CLAUDE_PROJECT` - Default project for `/project-next` from `~/Projects`. Set in `~/.bashrc`.
- `FLOW_WORKTREE_BASE` - Optional worktree base override (issue #584, ADR 0003 Option A): when set (host config, e.g. `~/.bashrc`), `/flow:start` + `/flow:auto` create worktrees at `$FLOW_WORKTREE_BASE/<repo>-<branch>` via the git lane instead of in-repo `.claude/worktrees/<branch>` via `EnterWorktree`. Unset = shipped default, byte-identical to today. Never set in shipped config (PR #527 norm).

## MCP Servers and Secrets

CPP ships **no container runtime** as of #469. The Docker MCP runtime (the `mcp-second-opinion` server, the `aws-secrets-agent` sidecar, all `docker-compose*.yml` files, every `make docker-*` target, and the compose-based deploy path) was retired when `mcp-second-opinion` moved to its own external repo (https://github.com/cooneycw/mcp-second-opinion). The remaining MCP servers are stdio/http and need no CPP-built image.

- **Second opinion (`/second-opinion:*`, `/evaluate:*`):** the server runs from its own external repo (localhost, or a Tailscale host). CPP consumes it as a client - the repo ships a root `.mcp.json` registering `second-opinion` as a streamable-http server at `http://127.0.0.1:8080/mcp`. Point that URL (or a user-scope `claude mcp add second-opinion --transport http --url <url> --scope user`) at wherever your server runs. Start the external server first; see `/cpp:init`.
- **Browser automation:** upstream `@playwright/mcp` registered via npx/stdio by `/cpp:init` (no container; the CPP `mcp-playwright-persistent` fork was retired in #423).
- **Secrets:** CPP stores no application secrets on disk and runs no secrets sidecar. The remaining AWS Secrets Manager consumers fetch **directly** via the AWS SDK/CLI: `essent-ai` (Woodpecker CI keys `WOODPECKER_URL` / `WOODPECKER_API_TOKEN`, consumed by `/flow:auto`, `woodpecker/bootstrap-secrets.py`, and `scripts/setup-woodpecker-cli.sh`; also holds `CPP_MEMORIES_DSN`, the common-memory Postgres DSN used by `lib/cpp_memory` for fleet-wide federation - reference the store host by its Tailscale address). Second-opinion LLM keys (`codex_llm_apikeys`) now live with the external server, not CPP. See `/secrets:*` and `lib/creds/`.
- **Deploy:** `make deploy` is an informative no-op - CPP ships no deployable services.
- **Secret scanning:** `make secret-scan` runs gitleaks locally (native binary or Docker fallback). Config in `.gitleaks.toml` with allowlists for doc/test false positives.
- **Bootstrap checks:** `make bootstrap-check` verifies admin-only prerequisites in `.claude/bootstrap.yaml` (now just `jq`, since the Docker runtime prerequisites were retired).
- **Woodpecker CI** runs on push/PR: secret-scan (gitleaks), lint, test, typecheck, and Dockerfile lint. The image-build / CVE-scan / SBOM / compose-policy / runtime-smoke stages were retired with the container runtime in #469.
- **Drift detection:** `make drift-check` compares host-installed artifacts against repo templates and flags **orphaned Docker MCP servers** - a leftover container, `mcp-<name>:*` image, or `claude`/`codex mcp` registration from a retired server (e.g. a lingering `mcp-second-opinion` or `aws-secrets-agent`) - against the curated `.claude/deprecated-mcps.yaml` list of record (via `scripts/mcp-drift.py`). Since CPP now ships no compose file, the current service set is empty by absence, so a listed server still present on the host is treated as an orphan. Detection is curated-list driven so a user's own custom MCP registration is never flagged (the valid external `second-opinion` registration is intentionally not listed); a **running** container that shares a deprecated name but belongs to an external compose project (or runs a non-CPP image) is also auto-protected by provenance and never torn down (issue #520), so the live external `second-opinion` / `aws-secrets-agent` containers survive `/cpp:update`. Teardown is per-server, user-confirmed, and keeps a newest-image restore point unless prune-all is chosen (run `/cpp:update`, or `python3 scripts/mcp-drift.py --teardown <name>`). See `docs/HOST_MANAGED_ARTIFACTS.md` for full inventory.
- **Reproducible builds:** the remaining container image references (the `mcp-evaluate` Dockerfile and the tool images in `.woodpecker.yml`) are pinned by version tag plus `@sha256:` digest, never `:latest`. `renovate.json` rotates the pinned digests on a weekly schedule so pinning never freezes security updates.

## Commands Reference

### Workflow
- `/flow:start` - Create worktree for an issue
- `/flow:eli5 <issue>` - Plain-language intent + necessity/staleness verdict + plan approval gate (runs after analyze, before implement)
- `/flow:check` - Run lint + test + security scan (no commit)
- `/flow:finish` - Quality gates, commit, push, create PR
- `/flow:deploy [target]` - Run make deploy + health/smoke checks
- `/flow:auto` - Full issue lifecycle in one shot (ELI5 plan/necessity approval gate between analyze and implement; `--yes` to skip the pause)
  - Optional second arg `PROJECT` targets a repo other than the session cwd (resolved as a path, else `~/Projects/<name>`); such cross-repo runs ride the deterministic git-worktree lane end-to-end instead of `EnterWorktree`, which cannot leave the session repo (#578)
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
remove` / `scripts/worktree-remove.sh` as the fallback. The base location is
configurable via `FLOW_WORKTREE_BASE` (issue #584, ADR 0003 Option A): when set,
worktrees are created at `$FLOW_WORKTREE_BASE/<repo>-<branch>` and the run rides
the #578 git lane end-to-end (the native tool's base dir is not configurable,
and out-of-repo `EnterWorktree(path=...)` triggers an unsuppressable approval
prompt); the guard/merge/remove/friction scripts resolve via git plumbing and
work unchanged at any base. The `/flow:*` commands
ship as the `flow` plugin (`/plugin install flow@cpp`): `.claude/commands/flow/*`
is the permanent source of truth and `plugins/flow/commands/*` holds
byte-identical copies kept in sync by `scripts/plugin-sync.sh`. The legacy
global-skill mirror (`~/.claude/skills/flow-*`) and its `flow-skill-sync.py`
generator were retired in B4 (#480).

**Worktree path-resolution rule (issue #486):** a native `EnterWorktree` session
edits the worktree, but the worktree lives *inside* the main repo at
`.claude/worktrees/<name>/`. Resolve every `Write`/`Edit` path from the active
worktree root - `git rev-parse --show-toplevel` - or use a plain relative path
from the session cwd; **never hand-build a `.claude/worktrees/<name>/...`
absolute path**, which has been observed to land the edit in the MAIN repo
working tree instead of the worktree (flow:auto #442 x2, #471). `/flow:auto`
Steps 4/6 run `scripts/flow-worktree-guard.sh` - an advisory, fail-open guard
that warns (never blocks) when a path this run edited is ALSO modified in the
main tree, the signature of a leaked edit - so the trap is caught before commit.
Pre-existing main dirt that does not overlap this run's edits is downgraded to a
quiet info note rather than a false leak warning (#536).

**Standalone skill extractions (issue #443):** skills with standalone value are
extracted to their own public plugin repos so users never have to clone CPP -
they install via `/plugin marketplace add cooneycw/<repo>` or `npx skills add
cooneycw/<repo>`, and improvement issues for an extracted skill are filed in
THAT repo, not here (the learnings->issue bridge, #463, routes there too). CPP
stays a consumer: it vendors the extracted skill's canonical core between
marker comments and layers its /flow wiring outside them; an advisory drift
script warns when the vendored copy falls behind. First extraction: the
`/flow:eli5` necessity gate -> https://github.com/cooneycw/eli5-gate
(core markers `eli5-core:begin`/`end` in `.claude/commands/flow/eli5.md`,
checked by `scripts/eli5-core-drift.sh`; reconcile drift by editing the
canonical repo first, then re-vendoring).

### Project
- `/project:init <name>` - Full project scaffolding (zero to GitHub repo)
- `/project-next` - Prioritized next-step report (compact default ~2-4K tokens; `--full` deep 5-tier analysis ~15-30K, `--brief` single pick)
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

**Spec-driven dev = official spec-kit plugin + `/flow:auto`.** CPP's home-grown pipeline (`/spec:create`, `/spec:sync`, `/spec:status`, `/spec:init`, backed by `lib/spec_bridge`) was **retired** in favor of upstream spec-kit (epic #417 Phase A, decision on #418).

### GitHub Issues
- `/github:issue-list` - List and search issues
- `/github:issue-create` - Create new issue
- `/github:issue-view` - View issue details
- `/github:issue-update` - Update existing issue
- `/github:issue-close` - Close issue with optional comment

**Scaffolding backend:** GitHub Issues (driven by the `flow-auto` skillset) is the only supported scaffolding/issue backend. Wiki.js and Plane are out of scope and are not part of CPP.

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

### Installation
The command/skill/hook surface installs via Claude Code's `/plugin` (ADR 0001, epic #417 Phase B): `/plugin marketplace add cooneycw/claude-power-pack` then `/plugin install <family>@cpp` for any of the 15 per-family plugins. `/plugin` owns versioning and updates for those surfaces. The `/cpp:*` commands below are no longer the way to get commands; they install and refresh only the **non-plugin infra** a plugin cannot deliver (external MCP server pointer, `@playwright/mcp` registration, secrets/AWS-SM access, spec-kit CLI, the PermissionRequest census hook, and the `/flow:*` allowlist merge). See `README.md` and `docs/HOST_MANAGED_ARTIFACTS.md`.

- `/cpp:init` - Non-plugin infra installer (Tiers: Minimal, Standard, Full, CI/CD, Codex); wires the external second-opinion `.mcp.json` pointer, `@playwright/mcp`, the census hook + flow allowlist, and optionally the spec-kit CLI (`specify`, the engine behind `/spec:adopt`)
- `/cpp:status` - Check installation state
- `/cpp:update` - Pull latest, sync deps, migrate legacy systemd units if present, tear down orphaned Docker MCP infra via the curated `.claude/deprecated-mcps.yaml` (Step 6c/7, user-confirmed; CPP ships no container runtime since #469), then offer to merge new flow allowlist rules from `templates/claude-settings-permissions.json` into `~/.claude/settings.json` (Step 7.5, user-confirmed) and to register the observe-only PermissionRequest census hook there (Step 7.6, user-confirmed); also refreshes the optional spec-kit CLI (`specify`) if installed (Step 4.6)

### Other
- `/dockers` - Docker container status, health, project linkages
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
  - `mode: external` - deploy runs out of band (host timer / CI on origin/main); `/flow:auto` Step 9 and `/flow:deploy` skip the inline `make deploy` rather than staging a throwaway per-worktree compose stack (#535)
  - `compose_project_name: <name>` - pins `COMPOSE_PROJECT_NAME` for `make deploy` so docker compose never derives it from a worktree/tmp directory basename and collides with fixed prod `container_name` values; defaults to the canonical primary-checkout name when unset (#535)
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
- **PermissionRequest hook** (`scripts/hook-permission-census.sh`) is an observe-only, fail-open permission-prompt census: it fires when a permission dialog is shown, derives a narrowest allow-rule candidate plus a risk tier (`READONLY-*`/`WRITE-LOCAL` -> allow candidate; `DESTRUCTIVE`/`CODE-EXEC`/net -> recorded but no candidate), and appends a `permission-prompt` record to the project's `.claude/friction.jsonl` for `/self-improvement:retro`. It captures the one friction class the model cannot observe (issue #482). Inherently-interactive tools (`AskUserQuestion`, `Skill`, `EnterPlanMode`, `ExitPlanMode`) are user-interaction dialogs, not permission friction, so they are skipped entirely rather than recorded as noise (issue #542). Registered user-level in `~/.claude/settings.json` (user-confirmed) by `/cpp:init` and `/cpp:update` Step 7.6 - never emits a permission decision.
- **SessionStart pending-retro reminder** (`scripts/hook-pending-retro.sh`) is an OPT-IN, fail-open, read-only reminder: when registered, it prints ONE advisory line at session open counting pending `.claude/friction.jsonl` signals (actionable vs the bulk permission-prompt census, separately) plus uncodified `Status: proposed` learnings, and points at `/self-improvement:retro`. It only SURFACES - never codifies, never blocks - and is silent when nothing is pending. Default OFF: deliberately NOT shipped in `.claude/hooks.json` (which `/cpp:init` copies into projects), so it never turns itself on; registered user-level in `~/.claude/settings.json` only on explicit opt-in (default N) by `/cpp:init` and `/cpp:update` Step 7.7 (issue #530).
- **Hooks configured in** `.claude/hooks.json` (SessionStart staleness + PostToolUse project-level) and `~/.claude/settings.json` (PermissionRequest census + opt-in SessionStart pending-retro reminder, user-level); the `secrets` plugin bundles the same PostToolUse masking hook for plugin installs (#479, ADR 0001 section 6)
- `/flow:finish` and `/flow:deploy` run the deterministic security scan (`lib/security`) as a quality gate
- CRITICAL findings block gates; HIGH findings produce warnings
- Configure gating in `.claude/security.yml` (optional, created by `/security:scan` when needed)
- For **semantic** code review (SQLi/XSS/authz/insecure handling), run native `/security-review` - not a CPP command
- **User-level flow allowlist** (`templates/claude-settings-permissions.json`) auto-approves the read-only git/gh plumbing that `/flow:*` runs, plus the audited flow helper-script family at its stable `~/.claude/scripts/` path (flow-start-resolve, flow-stale-check, flow-worktree-guard, flow-live-driver-guard, gh-pr-merge, worktree-remove - issue #581, invoked BARE so the prefix rules match); raw shipping actions (`git push`, `gh pr create`) and `cat` are deliberately excluded so gates and secret-read prompts stay intact. Merged via `/cpp:init` or `/cpp:update` Step 7.6; scripts re-linked by `/cpp:update` Step 5b; checked by `/flow:doctor`. Rationale: `templates/claude-settings-permissions.md`

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
