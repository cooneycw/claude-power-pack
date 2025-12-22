#!/bin/bash
#
# session-register.sh - Session lifecycle management
#
# Registers Claude Code sessions for coordination tracking.
# Called by hooks at SessionStart and Stop events.
#
# Usage:
#   session-register.sh start     # Register new session
#   session-register.sh pause     # Mark session as paused
#   session-register.sh end       # Deregister session
#   session-register.sh status    # Show all sessions
#   session-register.sh cleanup   # Remove dead sessions
#
# Environment:
#   CLAUDE_SESSION_ID - Session identifier (auto-generated if not set)
#   COORDINATION_DIR  - Override default ~/.claude/coordination
#

set -euo pipefail

# Configuration
COORDINATION_DIR="${COORDINATION_DIR:-$HOME/.claude/coordination}"
SESSION_DIR="$COORDINATION_DIR/sessions"
HEARTBEAT_DIR="$COORDINATION_DIR/heartbeat"
LOCK_DIR="$COORDINATION_DIR/locks"
CONFIG_FILE="$COORDINATION_DIR/config.json"

# Defaults
STALE_THRESHOLD=60

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Session ID - generate if not set
generate_session_id() {
    if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
        echo "$CLAUDE_SESSION_ID"
        return
    fi

    # Try to get a stable ID from terminal/process info
    if [[ -n "${TMUX_PANE:-}" ]]; then
        echo "tmux-${TMUX_PANE//[^a-zA-Z0-9]/-}"
    elif [[ -n "${TERM_SESSION_ID:-}" ]]; then
        echo "term-${TERM_SESSION_ID:0:16}"
    else
        echo "pid-$$-$(date +%s)"
    fi
}

CLAUDE_SESSION_ID="${CLAUDE_SESSION_ID:-$(generate_session_id)}"

# Ensure directories exist
init_dirs() {
    mkdir -p "$SESSION_DIR" "$HEARTBEAT_DIR" "$LOCK_DIR"
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        STALE_THRESHOLD=$(jq -r '.stale_threshold // 60' "$CONFIG_FILE" 2>/dev/null || echo 60)
    fi
}

# Extract issue number from path
extract_issue_number() {
    local path="$1"
    if [[ "$path" =~ issue-([0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

# Get repo name from git
get_repo_name() {
    local git_dir
    git_dir=$(git rev-parse --show-toplevel 2>/dev/null) || echo "unknown"
    basename "$git_dir"
}

# Check if session is alive (has recent heartbeat)
is_session_alive() {
    local session_id="$1"
    local heartbeat_file="$HEARTBEAT_DIR/${session_id}.heartbeat"

    if [[ ! -f "$heartbeat_file" ]]; then
        return 1
    fi

    local last_beat=$(stat -c %Y "$heartbeat_file" 2>/dev/null || echo 0)
    local now=$(date +%s)
    local age=$((now - last_beat))

    [[ $age -lt $STALE_THRESHOLD ]]
}

# Register a new session
register_session() {
    local session_file="$SESSION_DIR/${CLAUDE_SESSION_ID}.json"
    local cwd=$(pwd)
    local issue_num=$(extract_issue_number "$cwd")
    local repo_name=$(get_repo_name)
    local now=$(date -Iseconds)

    # Create session registration
    cat > "$session_file" << EOF
{
  "session_id": "$CLAUDE_SESSION_ID",
  "pid": $$,
  "ppid": $PPID,
  "cwd": "$cwd",
  "repo": "$repo_name",
  "issue": ${issue_num:-null},
  "started_at": "$now",
  "status": "active"
}
EOF

    # Create initial heartbeat
    touch "$HEARTBEAT_DIR/${CLAUDE_SESSION_ID}.heartbeat"

    # Export session ID for child processes
    export CLAUDE_SESSION_ID

    echo -e "${GREEN}Session registered:${NC} $CLAUDE_SESSION_ID"
    if [[ -n "$issue_num" ]]; then
        echo -e "  Issue: #$issue_num"
    fi
    echo -e "  Working directory: $cwd"
    echo -e "  Repo: $repo_name"
}

# Mark session as paused
pause_session() {
    local session_file="$SESSION_DIR/${CLAUDE_SESSION_ID}.json"

    if [[ ! -f "$session_file" ]]; then
        echo -e "${YELLOW}Session not registered, creating registration${NC}"
        register_session
        return
    fi

    # Update status to paused
    local tmp=$(mktemp)
    jq '.status = "paused" | .paused_at = "'"$(date -Iseconds)"'"' "$session_file" > "$tmp"
    mv "$tmp" "$session_file"

    echo -e "${YELLOW}Session paused:${NC} $CLAUDE_SESSION_ID"
}

# End/deregister session
end_session() {
    local session_file="$SESSION_DIR/${CLAUDE_SESSION_ID}.json"
    local heartbeat_file="$HEARTBEAT_DIR/${CLAUDE_SESSION_ID}.heartbeat"

    # Release any locks held by this session
    for lock_file in "$LOCK_DIR"/*.lock 2>/dev/null; do
        [[ -f "$lock_file" ]] || continue
        local holder=$(jq -r '.session_id // ""' "$lock_file" 2>/dev/null)
        if [[ "$holder" == "$CLAUDE_SESSION_ID" ]]; then
            local lock_name=$(basename "$lock_file" .lock)
            rm -f "$lock_file"
            echo -e "${YELLOW}Released lock:${NC} $lock_name"
        fi
    done

    # Remove session files
    rm -f "$session_file" "$heartbeat_file"
    echo -e "${GREEN}Session ended:${NC} $CLAUDE_SESSION_ID"
}

# Show status of all sessions
show_status() {
    echo -e "${BLUE}Session Coordination Status${NC}"
    echo "============================"
    echo ""
    echo -e "${CYAN}Current Session:${NC} $CLAUDE_SESSION_ID"
    echo ""

    echo -e "${CYAN}Registered Sessions:${NC}"
    echo ""

    local found=0
    for session_file in "$SESSION_DIR"/*.json 2>/dev/null; do
        [[ -f "$session_file" ]] || continue
        found=1

        local session_id=$(jq -r '.session_id // "unknown"' "$session_file")
        local cwd=$(jq -r '.cwd // "unknown"' "$session_file")
        local status=$(jq -r '.status // "unknown"' "$session_file")
        local issue=$(jq -r '.issue // "none"' "$session_file")
        local started_at=$(jq -r '.started_at // "unknown"' "$session_file")

        # Check if alive
        local alive_status=""
        if is_session_alive "$session_id"; then
            alive_status="${GREEN}(alive)${NC}"
        else
            alive_status="${RED}(stale)${NC}"
        fi

        # Get heartbeat age
        local heartbeat_file="$HEARTBEAT_DIR/${session_id}.heartbeat"
        local age="unknown"
        if [[ -f "$heartbeat_file" ]]; then
            local last_beat=$(stat -c %Y "$heartbeat_file" 2>/dev/null || echo 0)
            age=$(($(date +%s) - last_beat))
        fi

        # Highlight current session
        local prefix=""
        if [[ "$session_id" == "$CLAUDE_SESSION_ID" ]]; then
            prefix="${GREEN}*${NC} "
        else
            prefix="  "
        fi

        echo -e "${prefix}${BLUE}$session_id${NC} $alive_status"
        echo -e "    Status: $status"
        echo -e "    Issue: $issue"
        echo -e "    CWD: $cwd"
        echo -e "    Last heartbeat: ${age}s ago"
        echo ""
    done

    if [[ $found -eq 0 ]]; then
        echo "  (no registered sessions)"
        echo ""
    fi

    # Show active locks
    echo -e "${CYAN}Active Locks:${NC}"
    echo ""
    local lock_found=0
    for lock_file in "$LOCK_DIR"/*.lock 2>/dev/null; do
        [[ -f "$lock_file" ]] || continue
        lock_found=1

        local lock_name=$(basename "$lock_file" .lock)
        local holder=$(jq -r '.session_id // "unknown"' "$lock_file")
        local expires=$(jq -r '.expires_at // "unknown"' "$lock_file")

        echo -e "  ${YELLOW}$lock_name${NC}"
        echo -e "    Held by: $holder"
        echo -e "    Expires: $expires"
        echo ""
    done

    if [[ $lock_found -eq 0 ]]; then
        echo "  (no active locks)"
        echo ""
    fi
}

# Clean up dead sessions
cleanup_sessions() {
    echo -e "${BLUE}Cleaning up stale sessions...${NC}"
    echo ""

    local cleaned=0
    for session_file in "$SESSION_DIR"/*.json 2>/dev/null; do
        [[ -f "$session_file" ]] || continue

        local session_id=$(jq -r '.session_id // ""' "$session_file")
        if [[ -z "$session_id" ]]; then
            continue
        fi

        if ! is_session_alive "$session_id"; then
            # Release locks held by this session
            for lock_file in "$LOCK_DIR"/*.lock 2>/dev/null; do
                [[ -f "$lock_file" ]] || continue
                local holder=$(jq -r '.session_id // ""' "$lock_file" 2>/dev/null)
                if [[ "$holder" == "$session_id" ]]; then
                    local lock_name=$(basename "$lock_file" .lock)
                    rm -f "$lock_file"
                    echo -e "  ${YELLOW}Released stale lock:${NC} $lock_name (was held by $session_id)"
                fi
            done

            # Remove session files
            rm -f "$session_file" "$HEARTBEAT_DIR/${session_id}.heartbeat"
            echo -e "  ${RED}Removed stale session:${NC} $session_id"
            ((cleaned++))
        fi
    done

    if [[ $cleaned -eq 0 ]]; then
        echo "  No stale sessions found."
    else
        echo ""
        echo -e "${GREEN}Cleaned up $cleaned stale session(s)${NC}"
    fi
}

# Print usage
usage() {
    cat << 'EOF'
Usage: session-register.sh COMMAND

Commands:
  start     Register new session (called at SessionStart hook)
  pause     Mark session as paused (called at Stop hook)
  end       End session and release all locks
  status    Show all registered sessions and their state
  cleanup   Remove stale sessions and release their locks

Environment Variables:
  CLAUDE_SESSION_ID  Session identifier (auto-generated if not set)
  COORDINATION_DIR   Override default ~/.claude/coordination

This script is typically called by Claude Code hooks:
  - SessionStart -> session-register.sh start
  - Stop         -> session-register.sh pause

Examples:
  # View all sessions
  session-register.sh status

  # Clean up dead sessions
  session-register.sh cleanup
EOF
}

# Main
main() {
    init_dirs
    load_config

    local cmd="${1:-}"

    case "$cmd" in
        start)
            register_session
            ;;
        pause)
            pause_session
            ;;
        end)
            end_session
            ;;
        status)
            show_status
            ;;
        cleanup)
            cleanup_sessions
            ;;
        help|--help|-h)
            usage
            ;;
        "")
            usage
            exit 1
            ;;
        *)
            echo -e "${RED}Unknown command: $cmd${NC}" >&2
            usage
            exit 1
            ;;
    esac
}

main "$@"
