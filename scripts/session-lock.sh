#!/bin/bash
#
# session-lock.sh - Multi-session coordination locking utility
#
# Provides atomic file-based locking for Claude Code multi-session workflows.
# Uses mkdir for atomic lock acquisition (POSIX-compliant on all filesystems).
#
# Usage:
#   session-lock.sh acquire LOCK_NAME [TIMEOUT_SECONDS]
#   session-lock.sh release LOCK_NAME
#   session-lock.sh check LOCK_NAME
#   session-lock.sh list
#   session-lock.sh force-release LOCK_NAME
#   session-lock.sh wait LOCK_NAME [TIMEOUT_SECONDS]
#   session-lock.sh status
#   session-lock.sh info LOCK_NAME
#
# Environment:
#   CLAUDE_SESSION_ID - Session identifier (auto-generated if not set)
#   COORDINATION_DIR  - Override default ~/.claude/coordination
#
# Exit codes:
#   0 - Success
#   1 - Lock held by another session / operation failed
#   2 - Invalid arguments
#   3 - Timeout waiting for lock
#

set -euo pipefail

# Configuration
COORDINATION_DIR="${COORDINATION_DIR:-$HOME/.claude/coordination}"
LOCK_DIR="$COORDINATION_DIR/locks"
HEARTBEAT_DIR="$COORDINATION_DIR/heartbeat"
SESSION_DIR="$COORDINATION_DIR/sessions"
CONFIG_FILE="$COORDINATION_DIR/config.json"

# Defaults (can be overridden by config.json)
DEFAULT_TIMEOUT=300
STALE_THRESHOLD=60
MAX_WAIT_SECONDS=120

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Session ID - generate if not set
if [[ -z "${CLAUDE_SESSION_ID:-}" ]]; then
    # Try to get a stable ID from terminal/process info
    if [[ -n "${TMUX_PANE:-}" ]]; then
        CLAUDE_SESSION_ID="tmux-${TMUX_PANE//[^a-zA-Z0-9]/-}"
    else
        CLAUDE_SESSION_ID="pid-$$-$(date +%s)"
    fi
fi

# Ensure directories exist
init_dirs() {
    mkdir -p "$LOCK_DIR" "$HEARTBEAT_DIR" "$SESSION_DIR"

    # Create default config if not exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        cat > "$CONFIG_FILE" << 'EOF'
{
  "lock_timeout_default": 300,
  "heartbeat_interval": 30,
  "stale_threshold": 60,
  "strict_mode": true,
  "wait_on_conflict": true,
  "max_wait_seconds": 120
}
EOF
    fi
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        DEFAULT_TIMEOUT=$(jq -r '.lock_timeout_default // 300' "$CONFIG_FILE" 2>/dev/null || echo 300)
        STALE_THRESHOLD=$(jq -r '.stale_threshold // 60' "$CONFIG_FILE" 2>/dev/null || echo 60)
        MAX_WAIT_SECONDS=$(jq -r '.max_wait_seconds // 120' "$CONFIG_FILE" 2>/dev/null || echo 120)
    fi
}

# Log message with timestamp
log() {
    local level="$1"
    shift
    local msg="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case "$level" in
        INFO)  echo -e "${BLUE}[$timestamp]${NC} $msg" ;;
        OK)    echo -e "${GREEN}[$timestamp]${NC} $msg" ;;
        WARN)  echo -e "${YELLOW}[$timestamp]${NC} $msg" ;;
        ERROR) echo -e "${RED}[$timestamp]${NC} $msg" >&2 ;;
        *)     echo "[$timestamp] $msg" ;;
    esac
}

# Check if a session is alive (has recent heartbeat)
is_session_alive() {
    local session_id="$1"
    local heartbeat_file="$HEARTBEAT_DIR/${session_id}.heartbeat"

    if [[ ! -f "$heartbeat_file" ]]; then
        return 1  # No heartbeat file = dead
    fi

    local last_beat=$(stat -c %Y "$heartbeat_file" 2>/dev/null || echo 0)
    local now=$(date +%s)
    local age=$((now - last_beat))

    [[ $age -lt $STALE_THRESHOLD ]]
}

# Check if a PID is still running
is_pid_alive() {
    local pid="$1"
    kill -0 "$pid" 2>/dev/null
}

# Get lock info as JSON
get_lock_info() {
    local lock_name="$1"
    local lock_file="$LOCK_DIR/${lock_name}.lock"

    if [[ -f "$lock_file" ]]; then
        cat "$lock_file"
    else
        echo "{}"
    fi
}

# Check if lock is stale
is_lock_stale() {
    local lock_name="$1"
    local lock_file="$LOCK_DIR/${lock_name}.lock"

    if [[ ! -f "$lock_file" ]]; then
        return 0  # No lock = can acquire
    fi

    local holder_session=$(jq -r '.session_id // ""' "$lock_file" 2>/dev/null)
    local holder_pid=$(jq -r '.pid // 0' "$lock_file" 2>/dev/null)
    local expires_at=$(jq -r '.expires_at // ""' "$lock_file" 2>/dev/null)

    # Check if expired
    if [[ -n "$expires_at" ]]; then
        local expires_ts=$(date -d "$expires_at" +%s 2>/dev/null || echo 0)
        local now=$(date +%s)
        if [[ $now -gt $expires_ts ]]; then
            return 0  # Expired
        fi
    fi

    # Check if holder session is alive
    if [[ -n "$holder_session" ]] && ! is_session_alive "$holder_session"; then
        # Session dead, check PID as fallback
        if [[ "$holder_pid" != "0" ]] && ! is_pid_alive "$holder_pid"; then
            return 0  # Both session and PID dead
        fi
    fi

    return 1  # Lock is valid
}

# Acquire a lock
acquire_lock() {
    local lock_name="$1"
    local timeout="${2:-$DEFAULT_TIMEOUT}"
    local lock_file="$LOCK_DIR/${lock_name}.lock"
    local temp_dir="$LOCK_DIR/.${lock_name}.acquiring.$$"
    local wait_start=$(date +%s)

    while true; do
        # Check for stale lock and remove it
        if is_lock_stale "$lock_name"; then
            rm -f "$lock_file" 2>/dev/null || true
        fi

        # Check if lock exists and is valid
        if [[ -f "$lock_file" ]]; then
            local holder_session=$(jq -r '.session_id // "unknown"' "$lock_file" 2>/dev/null)
            local holder_worktree=$(jq -r '.worktree // "unknown"' "$lock_file" 2>/dev/null)
            local expires_at=$(jq -r '.expires_at // "unknown"' "$lock_file" 2>/dev/null)

            local now=$(date +%s)
            local waited=$((now - wait_start))

            if [[ $waited -ge $MAX_WAIT_SECONDS ]]; then
                log ERROR "Timeout waiting for lock: $lock_name (held by $holder_session)"
                return 3
            fi

            log WARN "Lock '$lock_name' held by session $holder_session ($holder_worktree). Waiting... (${waited}s/${MAX_WAIT_SECONDS}s)"
            sleep 2
            continue
        fi

        # Atomic lock acquisition using mkdir
        if mkdir "$temp_dir" 2>/dev/null; then
            # We got exclusive access to create the lock
            local now_iso=$(date -Iseconds)
            local expires_iso=$(date -d "+${timeout} seconds" -Iseconds)

            cat > "$lock_file" << EOF
{
  "session_id": "$CLAUDE_SESSION_ID",
  "worktree": "$(pwd)",
  "operation": "$lock_name",
  "acquired_at": "$now_iso",
  "pid": $$,
  "expires_at": "$expires_iso"
}
EOF
            rmdir "$temp_dir"

            # Update heartbeat
            touch "$HEARTBEAT_DIR/${CLAUDE_SESSION_ID}.heartbeat"

            log OK "Lock acquired: $lock_name (expires: $expires_iso)"
            return 0
        else
            # Race condition - someone else got the lock
            sleep 0.5
        fi
    done
}

# Release a lock
release_lock() {
    local lock_name="$1"
    local lock_file="$LOCK_DIR/${lock_name}.lock"

    if [[ ! -f "$lock_file" ]]; then
        log WARN "Lock '$lock_name' not found (already released?)"
        return 0
    fi

    local holder_session=$(jq -r '.session_id // ""' "$lock_file" 2>/dev/null)

    if [[ "$holder_session" != "$CLAUDE_SESSION_ID" ]]; then
        log ERROR "Cannot release lock '$lock_name' - held by different session: $holder_session"
        return 1
    fi

    rm -f "$lock_file"
    log OK "Lock released: $lock_name"
    return 0
}

# Check if lock is available
check_lock() {
    local lock_name="$1"
    local lock_file="$LOCK_DIR/${lock_name}.lock"

    if is_lock_stale "$lock_name"; then
        echo "available"
        return 0
    fi

    if [[ -f "$lock_file" ]]; then
        local holder_session=$(jq -r '.session_id // "unknown"' "$lock_file" 2>/dev/null)
        echo "held by $holder_session"
        return 1
    fi

    echo "available"
    return 0
}

# Force release a lock (admin override)
force_release_lock() {
    local lock_name="$1"
    local lock_file="$LOCK_DIR/${lock_name}.lock"

    if [[ ! -f "$lock_file" ]]; then
        log INFO "Lock '$lock_name' not found"
        return 0
    fi

    local holder_session=$(jq -r '.session_id // "unknown"' "$lock_file" 2>/dev/null)
    rm -f "$lock_file"
    log WARN "Force-released lock '$lock_name' (was held by $holder_session)"
    return 0
}

# Wait for a lock to be released
wait_for_lock() {
    local lock_name="$1"
    local timeout="${2:-$MAX_WAIT_SECONDS}"
    local lock_file="$LOCK_DIR/${lock_name}.lock"
    local start=$(date +%s)

    while true; do
        if is_lock_stale "$lock_name" || [[ ! -f "$lock_file" ]]; then
            log OK "Lock '$lock_name' is now available"
            return 0
        fi

        local now=$(date +%s)
        local waited=$((now - start))

        if [[ $waited -ge $timeout ]]; then
            log ERROR "Timeout waiting for lock '$lock_name' to be released"
            return 3
        fi

        local holder=$(jq -r '.session_id // "unknown"' "$lock_file" 2>/dev/null)
        log INFO "Waiting for lock '$lock_name' (held by $holder)... ${waited}s/${timeout}s"
        sleep 2
    done
}

# List all locks
list_locks() {
    local found=0

    echo "Active Locks:"
    echo "============="

    shopt -s nullglob
    for lock_file in "$LOCK_DIR"/*.lock; do
        [[ -f "$lock_file" ]] || continue
        found=1

        local lock_name=$(basename "$lock_file" .lock)
        local session_id=$(jq -r '.session_id // "unknown"' "$lock_file" 2>/dev/null)
        local worktree=$(jq -r '.worktree // "unknown"' "$lock_file" 2>/dev/null)
        local expires_at=$(jq -r '.expires_at // "unknown"' "$lock_file" 2>/dev/null)
        local acquired_at=$(jq -r '.acquired_at // "unknown"' "$lock_file" 2>/dev/null)

        # Calculate time remaining
        local expires_ts=$(date -d "$expires_at" +%s 2>/dev/null || echo 0)
        local now=$(date +%s)
        local remaining=$((expires_ts - now))

        local status="active"
        if is_lock_stale "$lock_name"; then
            status="STALE"
        fi

        echo ""
        echo -e "${BLUE}Lock:${NC} $lock_name ($status)"
        echo -e "  Session: $session_id"
        echo -e "  Worktree: $worktree"
        echo -e "  Acquired: $acquired_at"
        if [[ $remaining -gt 0 ]]; then
            echo -e "  Expires in: ${remaining}s"
        else
            echo -e "  Expired: ${expires_at}"
        fi
    done

    if [[ $found -eq 0 ]]; then
        echo "  (no active locks)"
    fi

    echo ""
    shopt -u nullglob
}

# Show lock info
show_lock_info() {
    local lock_name="$1"
    local lock_file="$LOCK_DIR/${lock_name}.lock"

    if [[ ! -f "$lock_file" ]]; then
        echo "Lock '$lock_name' is not held"
        return 1
    fi

    cat "$lock_file" | jq .
}

# Show overall status
show_status() {
    echo "Session Coordination Status"
    echo "==========================="
    echo ""
    echo -e "${BLUE}Current Session:${NC} $CLAUDE_SESSION_ID"
    echo -e "${BLUE}Working Directory:${NC} $(pwd)"
    echo -e "${BLUE}Coordination Dir:${NC} $COORDINATION_DIR"
    echo ""

    # Count locks
    local lock_count
    lock_count=$(find "$LOCK_DIR" -maxdepth 1 -name "*.lock" -type f 2>/dev/null | wc -l)
    echo -e "${BLUE}Active Locks:${NC} $lock_count"

    # Count sessions with recent heartbeats
    local session_count=0
    shopt -s nullglob
    for hb in "$HEARTBEAT_DIR"/*.heartbeat; do
        [[ -f "$hb" ]] || continue
        local age=$(($(date +%s) - $(stat -c %Y "$hb")))
        if [[ $age -lt $STALE_THRESHOLD ]]; then
            ((session_count++))
        fi
    done
    shopt -u nullglob
    echo -e "${BLUE}Active Sessions:${NC} $session_count"
    echo ""

    # Show config
    echo "Configuration:"
    echo "  Lock timeout: ${DEFAULT_TIMEOUT}s"
    echo "  Stale threshold: ${STALE_THRESHOLD}s"
    echo "  Max wait: ${MAX_WAIT_SECONDS}s"
}

# Print usage
usage() {
    cat << 'EOF'
Usage: session-lock.sh COMMAND [ARGS...]

Commands:
  acquire LOCK_NAME [TIMEOUT]  Acquire lock (blocks until acquired or timeout)
  release LOCK_NAME            Release a held lock
  check LOCK_NAME              Check if lock is available (exit 0) or held (exit 1)
  wait LOCK_NAME [TIMEOUT]     Wait for lock to be released (doesn't acquire)
  list                         List all active locks
  info LOCK_NAME               Show detailed info about a lock
  force-release LOCK_NAME      Force release (admin override for stale locks)
  status                       Show coordination system status

Examples:
  # Acquire lock for pytest (5 min timeout)
  session-lock.sh acquire pytest-nhl-api 300

  # Release lock after tests complete
  session-lock.sh release pytest-nhl-api

  # Check if PR creation is safe
  session-lock.sh check pr-nhl-api-issue-123

  # Wait for merge lock to be released
  session-lock.sh wait merge-nhl-api-main 60

  # List all current locks
  session-lock.sh list

  # Force-release a stale lock
  session-lock.sh force-release pytest-nhl-api

Environment Variables:
  CLAUDE_SESSION_ID  Session identifier (auto-generated if not set)
  COORDINATION_DIR   Override default ~/.claude/coordination

Exit Codes:
  0 - Success
  1 - Lock held by another session / operation failed
  2 - Invalid arguments
  3 - Timeout waiting for lock
EOF
}

# Main
main() {
    init_dirs
    load_config

    local cmd="${1:-}"
    shift || true

    case "$cmd" in
        acquire)
            [[ -n "${1:-}" ]] || { log ERROR "Lock name required"; exit 2; }
            acquire_lock "$1" "${2:-$DEFAULT_TIMEOUT}"
            ;;
        release)
            [[ -n "${1:-}" ]] || { log ERROR "Lock name required"; exit 2; }
            release_lock "$1"
            ;;
        check)
            [[ -n "${1:-}" ]] || { log ERROR "Lock name required"; exit 2; }
            check_lock "$1"
            ;;
        wait)
            [[ -n "${1:-}" ]] || { log ERROR "Lock name required"; exit 2; }
            wait_for_lock "$1" "${2:-$MAX_WAIT_SECONDS}"
            ;;
        list)
            list_locks
            ;;
        info)
            [[ -n "${1:-}" ]] || { log ERROR "Lock name required"; exit 2; }
            show_lock_info "$1"
            ;;
        force-release)
            [[ -n "${1:-}" ]] || { log ERROR "Lock name required"; exit 2; }
            force_release_lock "$1"
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            usage
            ;;
        "")
            usage
            exit 2
            ;;
        *)
            log ERROR "Unknown command: $cmd"
            usage
            exit 2
            ;;
    esac
}

main "$@"
