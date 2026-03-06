# Changelog

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
