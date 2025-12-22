# Changelog

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
- Django workflow commands
- Issue-driven development documentation
