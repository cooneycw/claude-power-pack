# Changelog

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
  | 🟢 Active | < 5 min | Fully blocked |
  | 🟡 Idle | 5 min - 1 hour | Blocked with warning |
  | 🟠 Stale | 1 - 4 hours | Override allowed |
  | ⚫ Abandoned | > 24 hours | Auto-released |

- **`get_session_status()`** function in `session-register.sh` returns tiered status
- **`format_age()`** helper for human-readable age display (e.g., "2m", "1h 30m")
- **`cleanup_abandoned()`** in `session-heartbeat.sh` for auto-releasing 24h+ claims
- **Status field** in `list-claims` JSON output for tiered display

### Changed

- **Threshold defaults**: Changed from 60s/5min to workday-appropriate values:
  - `ACTIVE_THRESHOLD`: 300s (5 minutes)
  - `IDLE_THRESHOLD`: 3600s (1 hour)
  - `STALE_THRESHOLD`: 14400s (4 hours)
  - `ABANDONED_THRESHOLD`: 86400s (24 hours)
- **`claim_issue()`**: Uses tiered logic instead of binary alive/stale check
- **`is_session_alive()`**: Now considers idle sessions (< 1 hour) as alive
- **`/project-next` and `/nhl-next`**: Updated documentation with tiered status display

### Fixed

- Session coordination was too aggressive - marking 3-minute-old sessions as "stale"
- Claims were shown as "available" prematurely during normal work breaks

---

## [1.9.1] - 2025-12-22

### Fixed

- **Terminal label state pollution across sessions** - Labels from one session were bleeding into other sessions due to two bugs:
  1. Legacy migration copied global state to every new subprocess
  2. Using `pid-$$` created unique state files per bash invocation (88 files in 2 hours)

### Changed

- **`terminal-label.sh`**: Renamed `get_session_id()` to `get_terminal_id()` with improved detection priority:
  - `CLAUDE_SESSION_ID` (explicit)
  - `TMUX_PANE` (stable per tmux pane)
  - `TTY` device (stable per terminal, e.g., `tty-pts-3`)
  - `TERM_SESSION_ID` (macOS Terminal)
  - `PPID` (fallback, more stable than `$$`)

### Removed

- Legacy state migration that was causing label pollution
- Orphaned `pid-*.state` files from previous implementation

### Technical Details

The override mechanism (`.last-set-override`) continues to bridge cases where terminal ID detection differs between `set` and `restore` calls (e.g., Bash tool vs hooks).

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
