# Changelog

## [Unreleased]

### Added

- **Browser session wrapper - named concurrent sessions (lease-desk)** (issue #421) -
  new `/browser:session` + `/browser:help` commands recover named **concurrent**
  browser sessions over upstream `@playwright/mcp` (the one feature upstream lacks,
  microsoft/playwright-mcp#1530) as a thin wrapper - no fork, no custom image. A fixed
  pool of pre-registered upstream instances ("desks", `playwright-desk-1..N`, run via
  `npx --isolated`) is leased by user-named sessions; each session's identity lives in a
  portable storage-state file (`.claude/playwright-state/<name>.json`), so sessions
  outlive desks - N desks multiplex unlimited named sessions, surviving restarts.
  The deterministic ledger `scripts/playwright-desk.py` (zero-dep stdlib) owns lease /
  release / idle-cleanup (`create`/`resume`/`save`/`close`/`list`/`cleanup`/`pool`,
  `--json` contract, 14 tests); the model drives each desk's `browser_*` MCP tools and
  the state files. `/cpp:init` gains an **opt-in** "browser pool" step (Full tier) that
  seeds `.claude/playwright-pool.json` from `templates/playwright-pool.example.json` and
  registers the desks. Design A (static pool) per the #419 spike - mid-session MCP
  registration is infeasible in Claude Code, so desks are pre-registered at startup;
  ratified by the #422 closure (owner chose the local wrapper over waiting on upstream).
  Guide: `docs/skills/browser-session-wrapper.md`.

- **Grill-me cycle: post-run friction retro (issue #426)** - the capture + local
  codify half of the compound-engineering loop (plan -> work -> assess -> codify).
  New always-on **capture** helper `scripts/friction-log.sh` (fail-open JSONL
  append to `.claude/friction.jsonl`) is woven into `/flow:auto` and `/flow:merge`
  so friction is recorded on every step of every run - success OR failure - because
  the richest friction (permission prompts, gate retries, red output) clusters on
  runs that fail partway, where a terminal retro would be blind. New **retro**
  command `/self-improvement:retro` grills the captured buffer + session, classifies
  the four friction classes, dedups against a persistent local ledger
  (`.claude/learnings.md`, seed `templates/learnings.md.example`) so applied/rejected
  fixes are never re-proposed, then proposes and (user-confirmed) applies codified
  fixes. Acceptance case demonstrated: run against the recorded pre-2026-07-03
  `/flow:auto` transcript (`tests/fixtures/retro/flow-auto-pre-eli5.md`) it emits
  exactly the 32-rule allowlist of `templates/claude-settings-permissions.json`
  (#427) unaided, excluding shipping/secret actions. Scope is bounded by trust
  boundary: per-machine `permissions.allow` fixes stay local and are never pushed to
  a shared store; portable knowledge/infra traps delegate to `/self-improvement:memory`
  (issue #433, common-memory substrate) when installed and degrade gracefully when
  not. Generalizes `/self-improvement:deployment` beyond deploys; standalone-
  extraction candidate (Phase C, alongside `flow-eli5`).
- **Flow read-only permission allowlist template** (issue #427) - new
  `templates/claude-settings-permissions.json` (+ rationale doc
  `templates/claude-settings-permissions.md`) codifies the 32 user-level
  permission rules that stop `/flow:*` from prompting for its read-only
  git/gh plumbing (issue reads, worktree creation, the branch-slug pipeline)
  on every run in every repo. `/cpp:init` gains an optional user-confirmed
  step that jq union-merges the template into `~/.claude/settings.json`
  (additive, idempotent - existing settings and rules preserved);
  `/cpp:update` Step 7.6 detects and offers to merge rules the template
  gained since the last update; `/flow:doctor` reports installed/missing
  rule counts with remediation. Shipping actions (`git push`, `gh pr
  create`) and `cat` stay deliberately excluded so the gate policy and
  secret-read prompts remain intact; the `sed -i` caveat is documented with
  a one-line opt-out. First codified-learning artifact for the grill-me
  cycle (#426).
- **C4 diagram rendering engine** (issue #411) - new zero-dependency Python
  renderer `scripts/c4-mermaid.py` replaces the removed `nano-banana` MCP server
  (#401) as the engine behind `/documentation:c4`. It consumes a JSON C4 model
  and emits **GitHub-renderable Mermaid**: L1-L3 as `flowchart` (with `subgraph`
  boundaries and C4 `classDef` colors) and L4 as `classDiagram` - deliberately
  avoiding the Mermaid C4 extension, which GitHub does not bundle and renders as
  raw text. Output is one `.mmd` per level plus an `index.md` (embeds every
  diagram in a ```mermaid fence, so the model renders inline on GitHub) and a
  `c4-manifest.json`. Restores an edge-validity QA gate (every edge/relation
  endpoint must reference a defined node; the command exits non-zero on invalid
  references) and flags dense diagrams (>20 nodes) for splitting. Rewires
  `.claude/commands/documentation/c4.md` and updates the `/documentation:c4`
  capability text in `.claude/skills/documentation.md` and
  `.claude/commands/documentation/help.md` (removing the interim "descoped"
  notes). Covered by `tests/test_c4_mermaid.py` (render output, QA validation,
  index/manifest, CLI exit codes, and a command-doc contract check). No new
  runtime dependency.
- **`/codex:ask` command** (issue #393) - new `.claude/commands/codex/ask.md`
  delegates a **read-only** question to Codex (`gpt-5.5`) via `codex exec
  --sandbox read-only` and relays the answer attributed to Codex - the
  question / second-opinion counterpart to the code-mutating `/codex:exec`
  and `/codex:auto`. Documents network opt-in (`--sandbox workspace-write -c
  sandbox_workspace_write.network_access=true`, scoped to a scratch dir, with
  prompt-injection / exfiltration caveats; only on explicit request) and
  background / long-running guidance. Promotes the personal `delegate`
  prototype skill into a first-class, shipped command listed in `/codex:help`,
  `/cpp:help`, `/cpp:init` (Tier 5), and the CLAUDE.md Codex Orchestration
  section.
- **Orphaned Docker MCP teardown in `/cpp:update`** (issue #405) - `/cpp:update`
  now detects and offers guided teardown of stale Docker MCP infrastructure left
  behind when a server is removed from `docker-compose.yml`: the old container,
  its `mcp-<name>:*` images, and any `claude`/`codex mcp` registration. Step 6c
  detects, Step 7 tears down per-server with confirmation (keeping the newest
  image tag as a restore point unless prune-all is chosen), mirroring the skill
  drift design (#395). `/cpp:status` surfaces orphaned Docker MCPs too, closing
  the blind spot where a removed server kept running unreported.
- `scripts/mcp-drift.py` - classifies deprecated MCP servers against the curated
  `.claude/deprecated-mcps.yaml` as ORPHANED DOCKER MCP / OK / ABSENT / UNKNOWN,
  with `--check`, `--json`, `--list-orphans`, `--plan`, and a guarded
  `--teardown` (`--prune-all-images` to drop the restore point). A server is
  orphaned only when it is on the list **and** gone from
  `docker compose config --services` (all profiles) **and** still present locally;
  teardown hard-refuses anything still shipped, absent, or not on the list - so a
  user's own custom MCP registration is never removed. Detection is curated-list
  driven, not a blanket "not in compose" sweep.
- `.claude/deprecated-mcps.yaml` - curated retired-MCP list of record (companion
  to `.claude/deprecated-skills.yaml`), seeded with `mcp-nano-banana` (#401),
  `mcp-woodpecker-ci` (#404), and the retired `mcp-coordination` server.
- `scripts/drift-detect.sh` - derives the current service set dynamically from
  `docker compose config --services` and flags orphaned Docker MCPs via
  `mcp-drift.py`, so a removed server is torn down instead of silently forgotten
  by the hardcoded server arrays.

### Changed

- **Trim `second-opinion` to OpenAI/Anthropic/Google** (issue #402) - the
  multi-provider experiment is retired. The second-opinion MCP server now
  exposes only the three reliable providers (Gemini, OpenAI, Anthropic) and no
  longer ships Mistral, Groq, OpenRouter (`:free` models), or DeepSeek. Removed
  their secret loaders, model/pricing catalog blocks, provider routing, and the
  now-unused OpenAI-compatible client machinery from `mcp-second-opinion/src/`;
  trimmed `DEFAULT_MODELS` to `gemini-3-pro, gpt-5.2, codex, o4-mini`. Dropped
  `MISTRAL_API_KEY`/`GROQ_API_KEY`/`OPENROUTER_API_KEY`/`DEEPSEEK_API_KEY` from
  the `docker-compose.yml` passthrough, the Makefile `codex_llm_apikeys`
  required-key set, `.env.example`, and the AWS secrets docs (the four keys can
  be deprovisioned from the `codex_llm_apikeys` secret separately). Deleted the
  `scripts/smoke-model-catalog.py` smoke test and its `second-opinion-model-smoke`
  Makefile target (they existed solely to exercise the removed OpenAI-compatible
  providers). Updated README/CLAUDE.md provider lists and the catalog/token-limit
  tests accordingly.

### Removed

- **Retire the `/skills:*` command family** (issue #437, epic #417 Phase A) - the
  six-command wrapper (`/skills:find|add|list|update|check|help`) around the
  `npx skills` CLI is fully absorbed by the native ecosystem: `npx skills`
  directly, the `/plugin` marketplace, auto-loaded `.claude/skills`, and
  `/reload-skills`. Deleted `.claude/commands/skills/` (all six command files)
  and the `skills-patterns` knowledge skill (`.claude/skills/skills-patterns.md`
  + `docs/skills/skills-patterns.md`). Docs repointed to the native path
  (`CLAUDE.md`, `README.md`, `/cpp:help`, `/cpp:init`, `/documentation:pptx`,
  `load-best-practices`, `best-practices`); the retirement is recorded in
  `.claude/deprecated-skills.yaml` for `/cpp:update` user-confirmed teardown.
  Note: no generated `skills-<verb>` skill mirrors ever existed - the family was
  hand-authored command files, so there was nothing extra to prune.
- **Retire the PreToolUse dangerous-command hook; keep PostToolUse secret-masking**
  (issue #439, epic #417 Phase A) - Claude Code's native destructive-git
  auto-blocking (v2.1.154) plus OS sandboxing now cover the cases the custom
  `hook-validate-command.sh` guarded (force-push to main, `git reset --hard`,
  `rm -rf /`, recursive `chmod`/`chown` on system dirs, `mkfs`/`fdisk`,
  kill-all), so the hook is redundant. Deleted `scripts/hook-validate-command.sh`
  and the `PreToolUse` block from `.claude/hooks.json` (leaving `SessionStart` +
  `PostToolUse`), and swept every reference in `.claude/commands/cpp/{init,status,update}.md`,
  `.claude/commands/flow/doctor.md`, `CLAUDE.md`, and `README.md`. The
  **PostToolUse secret-masking hook (`hook-mask-output.sh`) is retained** for
  both Bash and Read output: native tooling blocks credential *reads* but does
  not *mask* secrets that surface in output, so it stays additive. `/cpp:update`
  gains a guarded, user-confirmed cleanup step (Step 4.7) that removes a
  now-dangling `~/.claude/scripts/hook-validate-command.sh` symlink and strips
  the stale `PreToolUse` block from an already-copied project `hooks.json` - a
  dangling hook command exits non-zero and would otherwise block every Bash
  command. **Deliberate tradeoff:** the retired hook also carried best-effort SQL
  heuristics (`DROP TABLE`/`TRUNCATE`/`DELETE`-without-`WHERE`); these were regex
  warnings, not a real guardrail, and are **not** replaced by native
  blocking/sandbox - the #417 ecosystem review accepted this when it voted RETIRE.
- **Retire the `mcp-woodpecker-ci` MCP server** (issue #404) - the optional
  Woodpecker CI pipeline-management MCP (`cicd` profile, port 8085) was never
  adopted: not registered in any Claude/Codex client, no skill referenced its
  tools, and the one Woodpecker-touching workflow (`/flow:auto`) already calls
  the Woodpecker API directly via `curl`. Deleted `mcp-woodpecker-ci/` and
  removed the server from `docker-compose.yml` / `docker-compose.dev.yml`, the
  now-empty `cicd` compose profile membership (`aws-secrets-agent` is `core`-only
  again), the `.woodpecker.yml` MCP port export / build target / path filters,
  `renovate.json`, and the drift-detect / docker-health / runtime-smoke /
  check-docker-aws-env / codex-skill-gen scripts. Dropped the `cicd` profile
  from the user-facing Makefile targets and docs (`CLAUDE.md`, `README.md`,
  `.claude/commands/cpp/{init,status,update,help}.md`,
  `.claude/commands/dockers.md`, `docs/AWS_SECRETS_SIDECAR.md`) and pruned the
  matching `mcp-woodpecker-ci` assertions from
  `tests/test_docker_compose_config.py`. **Woodpecker CI as the deploy platform
  is unchanged** - the `.woodpecker.yml` pipeline logic (it still passes the now
  harmlessly-empty `--profile cicd`), `woodpecker/` server/agent configs,
  `lib/cicd/*`, the pipeline templates, `scripts/setup-woodpecker-cli.sh` /
  `scripts/assert-prod-env.sh`, and the `essent-ai` secret (`WOODPECKER_URL` /
  `WOODPECKER_API_TOKEN`, consumed by `/flow:auto`,
  `woodpecker/bootstrap-secrets.py`, and `scripts/setup-woodpecker-cli.sh`) are
  all retained.
- **Remove `nano-banana` MCP server; PPTX moves to the native Anthropic pptx skill**
  (issue #401) - the non-Anthropic (Gemini-backed) diagram + PowerPoint MCP experiment
  is retired. Deleted the `mcp-nano-banana/` server and its 7 tools
  (`list_diagram_types`, `generate_diagram`, `validate_diagram`, `split_diagram`,
  `create_pptx`, `validate_pptx_slides`, `diagram_to_pptx`), the `mcp-nano-banana`
  service from `docker-compose.yml` (port 8084, `core` profile), and every reference
  across `.woodpecker.yml` (image build/CVE/SBOM + smoke path filters), `pyproject.toml`,
  `Makefile`, `renovate.json`, `scripts/runtime-smoke.sh`, `scripts/drift-detect.sh`,
  and the docs/inventory commands. `/documentation:pptx` now delegates PowerPoint
  authoring to the native **`anthropics/skills@pptx`** skill (install via
  `npx skills add anthropics/skills@pptx`) and embeds only user-supplied diagram images.
  **C4 diagram image rendering is descoped**: `/documentation:c4` now writes a text C4
  model (`docs/architecture/c4-model.md`) and no longer renders HTML/PNG or runs density
  QA gating/splitting - choosing a replacement rendering engine is tracked in **#411**.
  Deleted the seven nano-banana-specific test modules (`test_dual_transport`,
  `test_c4_integration`, `test_split_diagram`, `test_density`, `test_wcag_contrast`,
  `test_validate_diagram`, `test_sanitize`) and pruned incidental nano-banana assertions
  from `test_docker_compose_config.py`, `test_docker_health_check.py`, and
  `test_deploy_scripts.py`. Drive-by: dropped the dead `mcp-coordination` entry from the
  mypy `exclude` (its directory was already removed). Follow-up orphan-teardown
  automation for machines that still have the old container/image is tracked in **#405**.

### Fixed

- **Prune dangling references to removed MCP servers** - follow-up cleanup of
  stragglers left after #401 (`nano-banana`) and #404 (`mcp-woodpecker-ci`) that still
  described removed tooling as current:
  - `scripts/drift-detect.sh`: removed the `check_go_binary` category that probed the
    deleted `~/go/bin/woodpecker-mcp` binary (it printed a phantom skip/drift line on
    every `make drift-check`); renumbered the remaining categories and the `--help`
    list. `tests/test_drift_detect.py`: dropped the removed `cicd` profile and
    `mcp-woodpecker-ci` service from the mocked `docker compose` output.
  - `docs/HOST_MANAGED_ARTIFACTS.md`: dropped the "Go Binary (Woodpecker MCP)" section
    and its `setup-go-binary.sh` timing-table row (the script was deleted with the
    server).
  - `.claude/commands/documentation/pptx.md`: replaced the "diagrams descoped,
    replacement tracked in #411" note (now shipped, PR #415) with guidance to render C4
    diagrams via `/documentation:c4` and embed the exported image.
  - `.claude/commands/cpp/update.md`: genericized the "new server in repo" example that
    named the removed `mcp-woodpecker-ci`.

### Removed

- **Retired CPP's home-grown spec pipeline** (issue #420, epic #417 Phase A) - deleted
  `lib/spec_bridge/` (~1.4K LOC: parser, issue_sync, status, CLI) plus its tests
  (`tests/test_spec_bridge_parser.py`, `tests/test_spec_bridge_status.py`), and the four
  legacy command files `.claude/commands/spec/{create,sync,init,status}.md`. Spec-driven
  development is now **the official GitHub spec-kit** (installed via `/spec:adopt`) for
  authoring plus `scripts/speckit-tasks-to-issues.sh` (gh-CLI issue sync) and `/flow:auto`
  for shipping - spec-kit's prompts are community-iterated and ship verification stages
  CPP lacked (`/speckit-clarify`, `/speckit-analyze`, `/speckit-checklist`). The spike
  (#418) confirmed no label adapter was needed and cut `/spec:status` (its bidirectional
  drift view queried `lib/spec_bridge`'s label scheme and had no upstream equivalent).
  The generated `spec-*` skills (`spec-create`, `spec-init`, `spec-status`, `spec-sync`,
  from the defunct `manifests/spec/` architecture; `spec-status`/`spec-sync` still
  targeted the retired Plane/Wiki.js backend) are recorded in
  `.claude/deprecated-skills.yaml` as a `spec` family so `/cpp:update` prunes them on
  installed machines. `/spec:adopt` and `/spec:help` survive; all consumers
  (`CLAUDE.md`, `README.md`, `/project-next`, `/project:init`, `/evaluate:*`,
  `mcp-evaluate`) were repointed to the spec-kit path.

## [7.2.0] - 2026-06-28

### Added

- **`/flow:eli5` command + `/flow:auto` approval gate** (issue #398) - new
  `.claude/commands/flow/eli5.md` runs after Analyze and before Implement and
  emits a reviewer-facing report: a plain-language (ELI5) restatement of the
  issue's intent, a necessity/staleness verdict (Still needed / Partially
  addressed / No longer needed / Needs reframing) backed by evidence from
  commits and PRs landed since the issue was filed, and the proposed changes
  pending approval. `/flow:auto` inserts it as Step 3 (lifecycle renumbered
  8 -> 9) and treats it as a gate: it pauses for plan approval by default
  (`--yes` / `--auto-approve`, or an `eli5: auto-approve` trailer, for
  unattended runs), and a `No longer needed` verdict routes to a close-issue
  recommendation instead of implementing. Registered in `flow/help.md`,
  `CLAUDE.md`, and `README.md`.
- **Skill drift/orphan detection in `/cpp:update`** (issue #395) - new Step 7.5
  detects retired and orphaned generated skills in `~/.claude/skills/` and offers
  guided, per-family, user-confirmed removal, mirroring the existing MCP/systemd
  drift handling.
- `scripts/skill-drift.py` - classifies generated skills against the curated
  `.claude/deprecated-skills.yaml` (DEPRECATED / ORPHANED / OK / IGNORED), with
  `--check`, `--json`, and a guarded `--prune` that moves skills to a timestamped
  backup (never `rm -rf`), refuses to touch OK/hand-authored skills, and blocks
  path traversal. Classification is curated-list driven, not a repo diff - a
  blanket diff would delete live skills since every generated skill references a
  retired `manifests/` source.
- `entire_family` flag in `.claude/deprecated-skills.yaml` - gates ORPHANED
  detection so a partially-deprecated family never flags its live members.

### Fixed

- **`drift-detect.sh` false "deployment model conflict"** (PR #400) - systemd
  unit presence is now derived from `systemctl show -p LoadState` (with an
  on-disk unit-file fallback) via a new `systemd_unit_exists` helper, instead of
  `systemctl is-active`, which returns `inactive` (exit 0) even for units that
  were never installed. On Docker-only hosts with no MCP systemd units, every
  running MCP server was wrongly flagged as a Docker/systemd deployment-model
  conflict and `make drift-check` exited non-zero. Adds a regression test.

## [7.1.0] - 2026-06-07

### Added

- **Skills ecosystem integration** - New `/skills:*` command family for discovering, installing, and managing agent skills from the [skills.sh](https://skills.sh/) ecosystem
- `/skills:find [QUERY]` - Search for skills by keyword or domain with quality vetting (install count, source reputation, GitHub stars)
- `/skills:add PACKAGE` - Install skills from GitHub or skills.sh with trust verification for third-party sources
- `/skills:list` - Show installed skills at project and global level
- `/skills:update` - Update all installed skills to latest versions
- `/skills:check` - Check for available updates without installing
- `/skills:help` - Skills commands overview
- Skills commands registered in `CLAUDE.md`, `cpp/help.md`

## [6.0.0] - 2026-05-31

### Breaking

- Docker with local builds is now the only supported MCP deployment model.
- Legacy systemd and venv-only MCP runtimes are removed as supported paths.

### Changed

- `/cpp:status` reports the deployment model as `Docker (local build)`.
- `/cpp:status` relabels systemd checks as `Legacy Systemd (migration required)`, reports `none (ok)` when clean, and points active legacy services to `/cpp:update`.
- `/cpp:update` is the migration path for tearing down legacy systemd units before Docker refresh.

## [5.2.0] - 2026-03-08

### Added - C4 Diagram QA Framework

- **`validate_diagram` MCP tool** - Diagram quality checks: duplicate IDs, edge validity, viewport fit, readability, orphan nodes, WCAG AA contrast, long labels (#255)
- **Node density scoring** - Automatic overflow detection based on viewport capacity heuristics; status levels: ok, warning, overflow, critical (#262)
- **`split_diagram` MCP tool** - Auto-splits large diagrams (>15 nodes) into summary + detail sub-diagrams with three clustering strategies: `c4_boundary`, `connectivity`, `type_group` (#263)
- **Multi-diagram L3/L4 generation** - `/documentation:c4` generates L3 for all containers and L4 for top 3 components per container (#258)
- **`c4-manifest.json`** - Tracks all generated diagrams with parent-child relationships, node/edge counts, and split roles (#259)
- **`index.html` navigation page** - Hierarchical browser for all C4 diagrams with level badges and metadata (#260)
- **Shared theme token system** - `ThemeTokens` dataclass provides consistent color palette across all diagram types via `theme_id` and `theme_tokens` parameters (#261)
- **QA gating in c4 and pptx skills** - Post-generation warning inspection: EDGE_INVALID triggers retry (max 2), OVERFLOW triggers split, ORPHAN/LABELS logged as warnings; QA summary in final reports (#264)
- **Playwright session optimization** - PPTX skill uses ONE browser session for all diagram screenshots (#264)
- **Comprehensive test suite** - 285 new tests: validation, density scoring, split strategy, XSS sanitization, WCAG contrast, C4 integration (#265)

### Fixed

- **XSS vulnerability** - HTML-escape all node labels and descriptions in diagram HTML output (#256)
- **WCAG AA color contrast** - All C4 and generic palettes updated to meet 4.5:1 minimum contrast ratio (#257)
- **test_wcag_contrast.py import** - Updated to use `_c4_color()` after theme token refactor (#264)

### Changed

- Version bump: 5.1.0 -> 5.2.0
- Nano-banana MCP tools: 4 -> 7 (added `validate_diagram`, `split_diagram`, `validate_pptx_slides`)
- Test count: 211 -> 496

---

## [5.0.0] - 2026-03-05

### Added - Wave 6: Polish, Quality & DX

- **`/secrets:delete` command** - Delete secrets from dotenv and AWS providers with audit logging (#121)
- **Stack-specific Makefile templates** - Django template (`django-uv.mk`) with manage.py targets; `/flow:doctor` now suggests framework-appropriate templates when no Makefile found (#122)
- **Django framework detection** - `lib/cicd/detector.py` promotes Python→Django when `manage.py` is present
- **Security gate documentation** - Expanded `/flow:help` and `/security:help` with gate behavior details (#123)

### Added - MCP Nano-Banana Server

- **MCP Nano-Banana** (`mcp-nano-banana/`, port 8084) - Diagram generation + PowerPoint creation (#161):
  - 4 MCP tools: `list_diagram_types`, `generate_diagram`, `create_pptx`, `diagram_to_pptx`
  - 6 diagram types: architecture, flowchart, sequence, orgchart, timeline, mindmap
  - 1920x1080 HTML diagrams with professional CSS themes
  - python-pptx integration for `.pptx` file creation
  - `/documentation:pptx` and `/documentation:c4` commands (replaces `/pptx:*`)

### Changed

- **Wave 6 Waves 1-4** completed:
  - Removed orphaned files and stale commands (#117)
  - Generalized QA skill for any project via `.claude/qa.yml` (#118)
  - Added 211 unit tests for Python libraries (`lib/cicd`, `lib/creds`, `lib/security`, `lib/spec_bridge`) (#119)
  - Consolidated MCP health checks into `/flow:doctor` and `/cpp:status` (#120)
- Fixed all 81 pre-existing ruff lint errors across codebase (#175)
- Version bump: 4.2.0 → 5.0.0

---

## [4.2.0] - 2026-03-04

### Added - Tier 4: CI/CD & Verification

- **`lib/cicd/` package** - Framework detection, Makefile generation, health checks, smoke tests (#141-#156):
  - `detector.py` - Auto-detect Python/Node/Go/Rust/Multi frameworks + package managers
  - `makefile.py` - Parse, validate, and generate Makefiles from templates
  - `health.py` - HTTP endpoint and process port health checks
  - `smoke.py` - Shell command smoke tests with exit code/output assertions
  - `pipeline.py` - GitHub Actions and Woodpecker CI pipeline generation
  - `container.py` - Dockerfile and docker-compose.yml generation
  - `config.py` - `.claude/cicd.yml` configuration schema
  - `models.py` - Framework, PackageManager, MakefileTarget, HealthCheckResult data models
- **7 Makefile templates** in `templates/makefiles/`: python-uv, python-pip, node-npm, node-yarn, go, rust, multi
- **CI/CD commands**: `/cicd:init`, `/cicd:check`, `/cicd:health`, `/cicd:smoke`, `/cicd:pipeline`, `/cicd:container`, `/cicd:help`
- **Tier 4 in `/cpp:init`** wizard - CI/CD tier added to installation flow (#152)
- **Post-deploy verification** - `/flow:deploy` and `/flow:finish` run health/smoke checks when configured (#147)
- **CI/CD diagnostics** in `/flow:doctor` (#153)
- **Woodpecker CI** local pipeline support alongside GitHub Actions (#155)
- **`/cicd-verification` skill** and updated CLAUDE.md (#154)
- **GitHub Actions workflow templates** in `templates/workflows/`
- **Container templates** in `templates/containers/`

### Added - Wave 7: Evaluate Flow

- **`/evaluate:issue` command** - 4-phase multi-model evaluation pipeline (#133-#135):
  - Phase 1: Multi-model divergence scan
  - Phase 2: Sequential reasoning (uses Sequential Thinking MCP if available)
  - Phase 3: Multi-model validation
  - Phase 4: Spec output to `.specify/specs/`
- **MCP Evaluate server** (`mcp-evaluate/`, port 8083) - Composite server with domain-aware prompting (#135)
  - 3 tools: `evaluate_start`, `evaluate_validate`, `evaluate_produce_spec`
  - Supports 5 domains: architecture, concept, algorithm, ui-design, workflow

### Added - Project Scaffolding

- **`/project:init` command** - Zero-to-GitHub-repo in one command (#156):
  - Framework-specific scaffolds (Python/uv, Node/npm, Go, Rust)
  - Auto-generates Makefile from detected framework
  - Installs CPP commands, skills, and hooks
  - Initializes `.specify/` for spec-driven development
  - Idempotent - safe to re-run if interrupted

### Changed

- **MCP servers switched to stdio transport** (recommended) with SSE as fallback (#138)
- **bash-prep workstation tuning** added to CPP install flow (#139)

---

## [4.0.0] - 2026-02-16

### Added - Wave 5: Simplified Workflow

- **`/flow` command set** - Stateless, git-native workflow (#87-#102):
  - `/flow:start` - Create worktree for issue
  - `/flow:status` - Show active worktrees
  - `/flow:finish` - Lint, test, commit, push, create PR
  - `/flow:merge` - Squash-merge PR, clean up worktree
  - `/flow:deploy` - Run `make deploy` with deploy logging
  - `/flow:sync` - Push WIP to remote for cross-machine pickup
  - `/flow:cleanup` - Prune stale worktrees and branches
  - `/flow:auto` - Full lifecycle in one command
  - `/flow:doctor` - Diagnose workflow environment
- **Makefile integration** as first-class deployment concept (#89)
- **`/security:*` commands** - Novice-friendly security scanning (#99):
  - `/security:scan`, `/security:quick`, `/security:deep`, `/security:explain`
  - `lib/security/` package with native scanners (gitignore, permissions, secrets, debug flags, env files)
  - External tool adapters (gitleaks, pip-audit, npm audit)
  - Flow gate integration (block on CRITICAL, warn on HIGH)
- **Enhanced secrets management** (#98):
  - Tiered architecture: dotenv-global → env-file → AWS Secrets Manager
  - `lib/creds/` package with bundle API, audit logging, project identity
  - FastAPI web UI for secret management
  - `/secrets:*` commands (get, set, list, run, validate, ui, rotate)
- **GPT-5.3-Codex and GPT-5.2-Codex** added to MCP Second Opinion (#85)

### Changed

- **Simplified hooks.json** - Removed session/heartbeat overhead (#90)
- **Redis coordination demoted to `extras/`** - No longer required for solo dev (#91)
- **`/project-next` simplified** to be worktree-focused (#92)
- **`/cpp:init` tiers updated** for simplified architecture (#95)
- **Package recommendations modernized** for uv compatibility (#97)

### Updated

- IDD docs and README for flow-based workflow (#94)
- Worktree/branch cleanup for stale local branches (#82)

---

## [3.0.0] - 2026-01-11

### Fixed

- MCP Second Opinion: systemd service missing User directive (#75)
- MCP Second Opinion: Missing hatch wheel build config (#74)
- MCP Second Opinion: Missing README.md causing uv sync failure (#73)
- MCP Second Opinion: google-genai API key property error on Python 3.14 (#76)
- MCP Second Opinion: Session tool-calling not functioning with Gemini 3 Pro (#83)
- MCP Coordination: Module import error (#70)
- `session-register.sh` cleanup command fails after first session (#69)
- Dead sessions not auto-cleaned from coordination registry (#81)
- `lib/secrets` renamed to `lib/creds` - no longer shadows Python stdlib `secrets` module (#59)
- Hardcoded absolute paths in `/load-best-practices` command (#49)

### Added

- MCP server discovery, health endpoints, and logging consistency (#62)
- Migrated from conda to uv with pyproject.toml (#65)
- Playwright-persistent accessibility improvements (#67)
- `/project-deploy` skill for deployment guidance (#57, #61)
- `/project-qa` commands for automated web testing (#58, #60)
- Browser-tiered capabilities architecture (#51, #55)
- `/cpp:init` handles full MCP server setup (#46)
- Disclose system environment changes during `cpp:init` (#47)

---

## [2.8.0] - 2025-12-24

### Added

- **Full README Documentation Update** - Comprehensive update covering all features:
  - **Quick Start: /cpp:init** - Promoted as main entry point with tiered installation
  - **Spec-Driven Development** - Full `.specify/` workflow with `/spec:*` commands
  - **MCP Playwright Persistent** - 29 browser automation tools (port 8081)
  - **MCP Coordination Server** - Redis-backed distributed locking (port 8082)
  - **Secrets Management** - `/secrets:*` commands with `lib/secrets/` Python module
  - **Environment Commands** - `/env:detect` for conda environment detection
  - **Security Hooks** - Secret masking and dangerous command blocking

### Changed

- Updated Quick Navigation to include all new sections
- Reorganized MCP section with three servers (Second Opinion, Playwright, Coordination)
- Updated Repository Structure tree to match CLAUDE.md
- Condensed What's New section for clarity

---

## [2.2.0] - 2025-12-24

### Added

- **MCP Coordination Server** (`mcp-coordination/`) - Redis-backed distributed locking:
  - 8 MCP tools: `acquire_lock`, `release_lock`, `check_lock`, `list_locks`, `register_session`, `heartbeat`, `session_status`, `health_check`
  - Wave/issue lock hierarchy: lock at issue, wave, or wave.issue level
  - Auto-detection: use "work" to lock based on current git branch
  - Session tracking with tiered status (active/idle/stale/abandoned)
  - Auto-expiry via Redis TTL for locks and heartbeats
  - Systemd service template for deployment

- **Redis installation** - Native Redis server for distributed coordination

### Changed

- Updated CLAUDE.md with MCP Coordination Server documentation
- Updated repository structure to include all 4 MCP servers
- Added port reference for all MCP servers (8080, 8081, 8082)

---

## [2.1.0] - 2025-12-24

### Changed

- **Replaced terminal labeling with shell prompt context** - More reliable approach:
  - Removed `terminal-label.sh` (unreliable due to TTY detection issues)
  - Added `prompt-context.sh` for PS1 integration
  - Context is always visible in shell prompt, no escape sequences needed

### Added

- **`scripts/prompt-context.sh`** - Generate worktree context for shell prompt
  - Auto-detects project prefix from `.claude-prefix` or repo name
  - Supports issue branches: `issue-42-auth` → `[CPP #42]`
  - Supports wave branches: `wave-5c.1-feature` → `[CPP W5c.1]`
  - Works with Bash and Zsh

### Removed

- **`scripts/terminal-label.sh`** - Replaced by prompt-context.sh
- Terminal label hooks from `.claude/hooks.json`

### Updated

- All documentation updated to reflect shell prompt approach
- CLAUDE.md, README.md, ISSUE_DRIVEN_DEVELOPMENT.md, CLAUDE_CODE_BEST_PRACTICES.md

---

## [1.9.2] - 2025-12-22

### Added

- **Tiered session staleness** - Realistic thresholds for team workflows:
  | Status | Heartbeat Age | Behavior |
  |--------|---------------|----------|
  | Active | < 5 min | Fully blocked |
  | Idle | 5 min - 1 hour | Blocked with warning |
  | Stale | 1 - 4 hours | Override allowed |
  | Abandoned | > 24 hours | Auto-released |

### Changed

- Threshold defaults updated to workday-appropriate values
- `claim_issue()` uses tiered logic instead of binary check

### Fixed

- Session coordination marking 3-minute-old sessions as "stale"

---

## [1.9.1] - 2025-12-22

### Fixed

- Terminal label state pollution across sessions

---

## [1.9.0] - 2025-12-21

### Added

- Project commands (`/project-lite`, `/project-next`)
- Session coordination scripts
- Terminal labeling system

## [1.8.0] - 2025-12-20

### Added

- GitHub issue management commands
- Issue-driven development documentation
