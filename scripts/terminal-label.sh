#!/bin/bash
# Terminal label management for Claude Code sessions
# Per-session state version - each session has its own label state
#
# Usage:
#   terminal-label.sh set "Label Text"           - Set label and save to state
#   terminal-label.sh await                      - Set to "awaiting" mode (no save)
#   terminal-label.sh restore                    - Restore from saved state
#   terminal-label.sh sync                       - Sync from session registration
#   terminal-label.sh issue [PREFIX] NUM [TITLE] - Set issue-specific label
#   terminal-label.sh project [PREFIX]           - Set project label (awaiting selection)
#   terminal-label.sh prefix [VALUE]             - Get/set default prefix
#   terminal-label.sh status                     - Show current configuration
#   terminal-label.sh cleanup-labels             - Remove orphaned label files
#
# Configuration (priority order):
#   1. TERMINAL_LABEL_PREFIX env var
#   2. .claude/.terminal-label-config (project-level)
#   3. ~/.claude/.terminal-label-config (user-level)
#   4. Default: "Issue"
#
# Session State:
#   Per-session state stored in ~/.claude/coordination/labels/{SESSION_ID}.state
#   Syncs with session registration in ~/.claude/coordination/sessions/{SESSION_ID}.json
#
# Examples:
#   terminal-label.sh issue NHL 123 "Player Landing"
#   # Result: "NHL #123: Player Landing"
#
#   TERMINAL_LABEL_PREFIX="Django" terminal-label.sh issue 45 "Auth Flow"
#   # Result: "Django #45: Auth Flow"
#
#   terminal-label.sh project NHL
#   # Result: "NHL: Select Next Action..."

# Debug logging - enable with TERMINAL_LABEL_DEBUG=1
log_debug() {
    if [[ "${TERMINAL_LABEL_DEBUG:-}" == "1" ]]; then
        local log_dir="${LABELS_DIR:-$HOME/.claude/coordination/labels}"
        mkdir -p "$log_dir" 2>/dev/null
        printf '%s %s\n' "$(date -Iseconds)" "$*" >> "$log_dir/debug.log"
    fi
}

# Terminal ID detection - uses stable identifiers that persist across subprocesses
# Priority: CLAUDE_SESSION_ID > TMUX_PANE > TTY (via /dev/tty) > SID > TERM_SESSION_ID > fallback
get_terminal_id() {
    # 1. Explicit session ID (set by Claude Code or hooks)
    if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
        log_debug "get_terminal_id: using CLAUDE_SESSION_ID=$CLAUDE_SESSION_ID"
        echo "$CLAUDE_SESSION_ID"
        return
    fi

    # 2. tmux pane - stable within a tmux session
    if [[ -n "${TMUX_PANE:-}" ]]; then
        log_debug "get_terminal_id: using TMUX_PANE=$TMUX_PANE"
        echo "tmux-${TMUX_PANE//[^a-zA-Z0-9]/-}"
        return
    fi

    # 3. TTY device - stable across subprocesses in same terminal
    local tty_path
    tty_path=$(tty 2>/dev/null) || tty_path=""
    if [[ -n "$tty_path" && "$tty_path" != "not a tty" ]]; then
        local tty_id="tty-${tty_path#/dev/}"
        tty_id="${tty_id//\//-}"
        log_debug "get_terminal_id: using TTY: $tty_id"
        echo "$tty_id"
        return
    fi

    # 4. Session ID (SID) from process tree - more stable than PPID across subshells
    local sid
    sid=$(ps -o sid= -p "${PPID:-$$}" 2>/dev/null | tr -d ' ')
    if [[ -n "$sid" && "$sid" != "0" ]]; then
        log_debug "get_terminal_id: using SID=$sid"
        echo "sid-$sid"
        return
    fi

    # 5. macOS Terminal session ID
    if [[ -n "${TERM_SESSION_ID:-}" ]]; then
        log_debug "get_terminal_id: using TERM_SESSION_ID"
        echo "term-${TERM_SESSION_ID:0:16}"
        return
    fi

    # 6. Fallback - use parent PID which is more stable than $$
    # PPID is the shell that spawned this script, usually the user's interactive shell
    log_debug "get_terminal_id: fallback to PPID=${PPID:-$$}"
    echo "ppid-${PPID:-$$}"
}

# Use terminal ID for label state (stable across subprocesses)
TERMINAL_ID="${TERMINAL_ID:-$(get_terminal_id)}"

# Per-session state paths
COORDINATION_DIR="${COORDINATION_DIR:-$HOME/.claude/coordination}"
LABELS_DIR="$COORDINATION_DIR/labels"
STATE_FILE="$LABELS_DIR/${TERMINAL_ID}.state"

# Per-terminal override file for set/restore coordination
# Each terminal gets its own override to prevent race conditions between terminals
OVERRIDE_FILE="$LABELS_DIR/${TERMINAL_ID}.override"

# Config files (shared across sessions)
USER_CONFIG="${HOME}/.claude/.terminal-label-config"
PROJECT_CONFIG=".claude/.terminal-label-config"
DEFAULT_AWAIT_LABEL="Claude: Awaiting Input..."
DEFAULT_PREFIX="Issue"

# Ensure directories exist
mkdir -p "$LABELS_DIR" 2>/dev/null

# Legacy migration removed - was causing state pollution across terminals
# Old behavior: copied global state to each new terminal, causing label bleed
# New behavior: each terminal starts fresh until explicitly set

# Function to get prefix from config files or env
get_prefix() {
    # 1. Environment variable (highest priority)
    if [[ -n "$TERMINAL_LABEL_PREFIX" ]]; then
        echo "$TERMINAL_LABEL_PREFIX"
        return
    fi

    # 2. Project-level config
    if [[ -f "$PROJECT_CONFIG" ]]; then
        local prefix
        prefix=$(grep -E "^DEFAULT_PREFIX=" "$PROJECT_CONFIG" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        if [[ -n "$prefix" ]]; then
            echo "$prefix"
            return
        fi
    fi

    # 3. User-level config
    if [[ -f "$USER_CONFIG" ]]; then
        local prefix
        prefix=$(grep -E "^DEFAULT_PREFIX=" "$USER_CONFIG" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        if [[ -n "$prefix" ]]; then
            echo "$prefix"
            return
        fi
    fi

    # 4. Default
    echo "$DEFAULT_PREFIX"
}

# Function to set terminal title
# Outputs directly to /dev/tty to ensure it reaches the terminal even in subprocesses
set_title() {
    local title="$1"
    log_debug "set_title: setting title to '$title'"

    # OSC escape sequence for terminal title - write directly to /dev/tty
    # This ensures the escape sequence reaches the terminal even when stdout is piped
    # Use a subshell to suppress errors when /dev/tty isn't accessible
    if [ -c /dev/tty ]; then
        (printf '\033]0;%s\007' "$title" > /dev/tty) 2>/dev/null || printf '\033]0;%s\007' "$title"
    else
        # Fallback to stdout if /dev/tty doesn't exist
        printf '\033]0;%s\007' "$title"
    fi

    # Also try tmux if available
    if [[ -n "${TMUX:-}" ]]; then
        tmux rename-window "$title" 2>/dev/null || true
    fi
}

# Function to save current label to state file
save_label() {
    local label="$1"
    local prefix="$2"
    cat > "$STATE_FILE" << EOF
LABEL="$label"
PREFIX="$prefix"
TIMESTAMP="$(date -Iseconds)"
EOF
}

# Function to read saved label
read_label() {
    if [[ -f "$STATE_FILE" ]]; then
        grep -E "^LABEL=" "$STATE_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"'
    else
        echo ""
    fi
}

# Function to read saved prefix
read_saved_prefix() {
    if [[ -f "$STATE_FILE" ]]; then
        grep -E "^PREFIX=" "$STATE_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"'
    else
        echo ""
    fi
}

# Sync label from session registration (authoritative source)
# Note: Session registration uses a different ID scheme than terminal labels
sync_from_session() {
    local session_file="$COORDINATION_DIR/sessions/${TERMINAL_ID}.json"
    if [[ -f "$session_file" ]]; then
        local label
        label=$(jq -r '.terminal_label // empty' "$session_file" 2>/dev/null)
        if [[ -n "$label" ]]; then
            local prefix
            prefix=$(jq -r '.claim.label_prefix // "Issue"' "$session_file" 2>/dev/null)
            save_label "$label" "$prefix"
            echo "$label"
            return 0
        fi
    fi
    return 1
}

# Cleanup stale label files
cleanup_labels() {
    echo "Cleaning up stale label files..."
    local cleaned=0

    for state_file in "$LABELS_DIR"/*.state; do
        [[ -f "$state_file" ]] || continue

        local session_id
        session_id=$(basename "$state_file" .state)
        local session_reg="$COORDINATION_DIR/sessions/${session_id}.json"
        local heartbeat="$COORDINATION_DIR/heartbeat/${session_id}.heartbeat"

        # Remove if no session registration exists
        if [[ ! -f "$session_reg" ]]; then
            rm -f "$state_file"
            echo "  Removed orphaned: $session_id"
            ((cleaned++))
            continue
        fi

        # Remove if heartbeat is stale (>5 minutes)
        if [[ -f "$heartbeat" ]]; then
            local last_beat age
            # Cross-platform: Linux uses -c %Y, macOS uses -f %m
            last_beat=$(stat -c %Y "$heartbeat" 2>/dev/null || stat -f %m "$heartbeat" 2>/dev/null || echo 0)
            age=$(($(date +%s) - last_beat))
            if [[ $age -gt 300 ]]; then
                rm -f "$state_file"
                echo "  Removed stale: $session_id (${age}s old)"
                ((cleaned++))
            fi
        fi
    done

    if [[ $cleaned -eq 0 ]]; then
        echo "  No stale label files found."
    else
        echo "Cleaned up $cleaned label file(s)."
    fi
}

# Main command handling
case "$1" in
    set)
        label="${2:-Claude Code}"
        prefix=$(get_prefix)
        set_title "$label"
        save_label "$label" "$prefix"
        # Write per-terminal override for set/restore coordination
        log_debug "set: writing override to $OVERRIDE_FILE"
        echo "$label" > "$OVERRIDE_FILE"
        ;;

    await)
        # Set awaiting label without overwriting saved state
        set_title "$DEFAULT_AWAIT_LABEL"
        ;;

    restore)
        log_debug "restore: checking override file $OVERRIDE_FILE"
        # Check for recent override (within 5 seconds)
        # Solves race condition when TTY detection varies between set and restore calls
        if [[ -f "$OVERRIDE_FILE" ]]; then
            # Cross-platform: Linux uses -c %Y, macOS uses -f %m
            local override_mtime
            override_mtime=$(stat -c %Y "$OVERRIDE_FILE" 2>/dev/null || stat -f %m "$OVERRIDE_FILE" 2>/dev/null || echo 0)
            override_age=$(($(date +%s) - override_mtime))
            log_debug "restore: override age=${override_age}s"
            if [[ $override_age -lt 5 ]]; then
                override_label=$(cat "$OVERRIDE_FILE" 2>/dev/null)
                if [[ -n "$override_label" ]]; then
                    log_debug "restore: using override label '$override_label'"
                    set_title "$override_label"
                    rm -f "$OVERRIDE_FILE"  # One-time use
                    exit 0
                fi
            fi
            rm -f "$OVERRIDE_FILE"  # Expired, clean up
        fi

        # First try to sync from session registration (authoritative source)
        synced_label=$(sync_from_session)
        if [[ -n "$synced_label" ]]; then
            set_title "$synced_label"
        else
            # Fall back to per-session state file
            saved=$(read_label)
            if [[ -n "$saved" ]]; then
                set_title "$saved"
            fi
        fi
        ;;

    sync)
        # Force sync from session registration
        synced=$(sync_from_session)
        if [[ -n "$synced" ]]; then
            set_title "$synced"
            echo "Synced from session: $synced"
        else
            echo "No session label found for: $TERMINAL_ID"
        fi
        ;;

    cleanup-labels)
        cleanup_labels
        ;;

    issue)
        # Parse arguments: issue [PREFIX] NUM [TITLE]
        # If $2 is a number, it's the issue number (use default prefix)
        # If $2 is not a number, it's the prefix
        if [[ "$2" =~ ^[0-9]+$ ]]; then
            # $2 is the issue number
            prefix=$(get_prefix)
            num="$2"
            title="$3"
        else
            # $2 is the prefix
            prefix="${2:-$(get_prefix)}"
            num="$3"
            title="$4"
        fi

        if [[ -n "$num" ]] && [[ -n "$title" ]]; then
            label="${prefix} #${num}: ${title}"
        elif [[ -n "$num" ]]; then
            label="${prefix} #${num}"
        else
            label="${prefix}"
        fi
        set_title "$label"
        save_label "$label" "$prefix"
        ;;

    project)
        prefix="${2:-$(get_prefix)}"
        label="${prefix}: Select Next Action..."
        set_title "$label"
        save_label "$label" "$prefix"
        ;;

    prefix)
        if [[ -n "$2" ]]; then
            # Set prefix in user config
            mkdir -p "$(dirname "$USER_CONFIG")"
            if [[ -f "$USER_CONFIG" ]]; then
                # Update existing config
                if grep -q "^DEFAULT_PREFIX=" "$USER_CONFIG" 2>/dev/null; then
                    sed -i "s/^DEFAULT_PREFIX=.*/DEFAULT_PREFIX=\"$2\"/" "$USER_CONFIG"
                else
                    echo "DEFAULT_PREFIX=\"$2\"" >> "$USER_CONFIG"
                fi
            else
                echo "DEFAULT_PREFIX=\"$2\"" > "$USER_CONFIG"
            fi
            echo "Prefix set to: $2"
        else
            # Get current prefix
            echo "Current prefix: $(get_prefix)"
        fi
        ;;

    status)
        echo "=== Terminal Label Configuration ==="
        echo "Terminal ID: $TERMINAL_ID"
        echo "State file: $STATE_FILE"
        echo "User config: $USER_CONFIG"
        echo "Project config: $PROJECT_CONFIG"
        echo ""
        echo "Current prefix: $(get_prefix)"
        echo "Saved label: $(read_label)"
        echo "Saved prefix: $(read_saved_prefix)"
        echo ""

        # Check session registration
        session_file="$COORDINATION_DIR/sessions/${TERMINAL_ID}.json"
        if [[ -f "$session_file" ]]; then
            session_label=$(jq -r '.terminal_label // "none"' "$session_file" 2>/dev/null)
            claimed_issue=$(jq -r '.claim.issue_number // "none"' "$session_file" 2>/dev/null)
            echo "Session registration:"
            echo "  Terminal label: $session_label"
            echo "  Claimed issue: $claimed_issue"
        else
            echo "Session registration: (not registered)"
        fi
        echo ""

        if [[ -n "$TERMINAL_LABEL_PREFIX" ]]; then
            echo "TERMINAL_LABEL_PREFIX env var: $TERMINAL_LABEL_PREFIX"
        fi
        ;;

    *)
        echo "Terminal Label Manager for Claude Code"
        echo "Per-session state version"
        echo ""
        echo "Usage: $0 <command> [args...]"
        echo ""
        echo "Commands:"
        echo "  set <label>              Set terminal title and save"
        echo "  await                    Set to 'awaiting input' mode"
        echo "  restore                  Restore saved label (syncs from session first)"
        echo "  sync                     Force sync from session registration"
        echo "  issue [PREFIX] NUM [TITLE]  Set issue-specific label"
        echo "  project [PREFIX]         Set project label"
        echo "  prefix [VALUE]           Get/set default prefix"
        echo "  status                   Show current configuration"
        echo "  cleanup-labels           Remove orphaned label files"
        echo ""
        echo "Terminal: $TERMINAL_ID"
        echo "State:    $STATE_FILE"
        echo ""
        echo "Examples:"
        echo "  $0 issue 42 'Fix login bug'"
        echo "  $0 issue NHL 123 'Player Landing'"
        echo "  $0 project MyApp"
        echo "  $0 prefix Django"
        exit 1
        ;;
esac
