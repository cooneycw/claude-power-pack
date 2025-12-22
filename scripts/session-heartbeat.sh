#!/bin/bash
#
# session-heartbeat.sh - Session heartbeat management
#
# Maintains heartbeat files for session liveness detection.
# Called by hooks at UserPromptSubmit events.
#
# Usage:
#   session-heartbeat.sh touch         # Update heartbeat timestamp
#   session-heartbeat.sh daemon        # Run as background heartbeat daemon
#   session-heartbeat.sh check ID      # Check if session is alive
#   session-heartbeat.sh age [ID]      # Get heartbeat age in seconds
#
# Environment:
#   CLAUDE_SESSION_ID - Session identifier
#   COORDINATION_DIR  - Override default ~/.claude/coordination
#

set -euo pipefail

# Configuration
COORDINATION_DIR="${COORDINATION_DIR:-$HOME/.claude/coordination}"
HEARTBEAT_DIR="$COORDINATION_DIR/heartbeat"
CONFIG_FILE="$COORDINATION_DIR/config.json"

# Defaults
HEARTBEAT_INTERVAL=30
STALE_THRESHOLD=60

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Session ID
generate_session_id() {
    if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
        echo "$CLAUDE_SESSION_ID"
        return
    fi

    if [[ -n "${TMUX_PANE:-}" ]]; then
        echo "tmux-${TMUX_PANE//[^a-zA-Z0-9]/-}"
    elif [[ -n "${TERM_SESSION_ID:-}" ]]; then
        echo "term-${TERM_SESSION_ID:0:16}"
    else
        echo "pid-$$-$(date +%s)"
    fi
}

CLAUDE_SESSION_ID="${CLAUDE_SESSION_ID:-$(generate_session_id)}"
HEARTBEAT_FILE="$HEARTBEAT_DIR/${CLAUDE_SESSION_ID}.heartbeat"

# Ensure directories exist
init_dirs() {
    mkdir -p "$HEARTBEAT_DIR"
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        HEARTBEAT_INTERVAL=$(jq -r '.heartbeat_interval // 30' "$CONFIG_FILE" 2>/dev/null || echo 30)
        STALE_THRESHOLD=$(jq -r '.stale_threshold // 60' "$CONFIG_FILE" 2>/dev/null || echo 60)
    fi
}

# Update heartbeat timestamp
touch_heartbeat() {
    touch "$HEARTBEAT_FILE"
}

# Run heartbeat daemon in background
run_daemon() {
    # Create PID file
    local pid_file="$HEARTBEAT_DIR/${CLAUDE_SESSION_ID}.daemon.pid"

    # Check if already running
    if [[ -f "$pid_file" ]]; then
        local existing_pid=$(cat "$pid_file")
        if kill -0 "$existing_pid" 2>/dev/null; then
            echo "Heartbeat daemon already running (PID: $existing_pid)"
            return 0
        fi
    fi

    # Fork and run in background
    (
        echo $$ > "$pid_file"
        trap "rm -f '$pid_file'" EXIT

        while true; do
            touch "$HEARTBEAT_FILE"
            sleep "$HEARTBEAT_INTERVAL"
        done
    ) &

    disown
    echo "Heartbeat daemon started (PID: $!)"
}

# Stop heartbeat daemon
stop_daemon() {
    local pid_file="$HEARTBEAT_DIR/${CLAUDE_SESSION_ID}.daemon.pid"

    if [[ ! -f "$pid_file" ]]; then
        echo "No daemon running for session $CLAUDE_SESSION_ID"
        return 0
    fi

    local pid=$(cat "$pid_file")
    if kill "$pid" 2>/dev/null; then
        rm -f "$pid_file"
        echo "Heartbeat daemon stopped (PID: $pid)"
    else
        rm -f "$pid_file"
        echo "Daemon was not running (stale PID file removed)"
    fi
}

# Check if a session is alive
check_session() {
    local session_id="${1:-$CLAUDE_SESSION_ID}"
    local hb_file="$HEARTBEAT_DIR/${session_id}.heartbeat"

    if [[ ! -f "$hb_file" ]]; then
        echo -e "${RED}dead${NC} (no heartbeat file)"
        return 1
    fi

    local last_beat=$(stat -c %Y "$hb_file" 2>/dev/null || echo 0)
    local now=$(date +%s)
    local age=$((now - last_beat))

    if [[ $age -lt $STALE_THRESHOLD ]]; then
        echo -e "${GREEN}alive${NC} (last heartbeat: ${age}s ago)"
        return 0
    else
        echo -e "${YELLOW}stale${NC} (last heartbeat: ${age}s ago, threshold: ${STALE_THRESHOLD}s)"
        return 1
    fi
}

# Get heartbeat age
get_age() {
    local session_id="${1:-$CLAUDE_SESSION_ID}"
    local hb_file="$HEARTBEAT_DIR/${session_id}.heartbeat"

    if [[ ! -f "$hb_file" ]]; then
        echo "-1"
        return 1
    fi

    local last_beat=$(stat -c %Y "$hb_file" 2>/dev/null || echo 0)
    local now=$(date +%s)
    echo $((now - last_beat))
}

# List all heartbeats
list_heartbeats() {
    echo "Session Heartbeats"
    echo "=================="
    echo ""

    local found=0
    for hb_file in "$HEARTBEAT_DIR"/*.heartbeat 2>/dev/null; do
        [[ -f "$hb_file" ]] || continue
        found=1

        local session_id=$(basename "$hb_file" .heartbeat)
        local last_beat=$(stat -c %Y "$hb_file" 2>/dev/null || echo 0)
        local age=$(($(date +%s) - last_beat))

        local status
        if [[ $age -lt $STALE_THRESHOLD ]]; then
            status="${GREEN}alive${NC}"
        else
            status="${RED}stale${NC}"
        fi

        local current=""
        if [[ "$session_id" == "$CLAUDE_SESSION_ID" ]]; then
            current=" ${YELLOW}(current)${NC}"
        fi

        echo -e "  $session_id: ${age}s ago [$status]$current"
    done

    if [[ $found -eq 0 ]]; then
        echo "  (no heartbeat files)"
    fi
    echo ""
}

# Print usage
usage() {
    cat << 'EOF'
Usage: session-heartbeat.sh COMMAND [ARGS]

Commands:
  touch           Update heartbeat timestamp (called by UserPromptSubmit hook)
  daemon          Start background heartbeat daemon
  stop            Stop heartbeat daemon
  check [ID]      Check if session is alive (default: current session)
  age [ID]        Get heartbeat age in seconds
  list            List all session heartbeats

Environment Variables:
  CLAUDE_SESSION_ID  Session identifier (auto-generated if not set)
  COORDINATION_DIR   Override default ~/.claude/coordination

Configuration (from config.json):
  heartbeat_interval  Seconds between daemon heartbeats (default: 30)
  stale_threshold     Seconds before heartbeat considered stale (default: 60)

This script is typically called by Claude Code hooks:
  - UserPromptSubmit -> session-heartbeat.sh touch

Examples:
  # Quick heartbeat update
  session-heartbeat.sh touch

  # Check if a specific session is alive
  session-heartbeat.sh check session-abc123

  # View all heartbeats
  session-heartbeat.sh list
EOF
}

# Main
main() {
    init_dirs
    load_config

    local cmd="${1:-}"
    shift || true

    case "$cmd" in
        touch)
            touch_heartbeat
            ;;
        daemon)
            run_daemon
            ;;
        stop)
            stop_daemon
            ;;
        check)
            check_session "${1:-}"
            ;;
        age)
            get_age "${1:-}"
            ;;
        list)
            list_heartbeats
            ;;
        help|--help|-h)
            usage
            ;;
        "")
            # Default: just touch heartbeat (for hook efficiency)
            touch_heartbeat
            ;;
        *)
            echo -e "${RED}Unknown command: $cmd${NC}" >&2
            usage
            exit 1
            ;;
    esac
}

main "$@"
