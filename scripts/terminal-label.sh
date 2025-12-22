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

# Session ID detection (same as session-register.sh)
get_session_id() {
    if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
        echo "$CLAUDE_SESSION_ID"
        return
    fi

    if [[ -n "${TMUX_PANE:-}" ]]; then
        echo "tmux-${TMUX_PANE//[^a-zA-Z0-9]/-}"
    elif [[ -n "${TERM_SESSION_ID:-}" ]]; then
        echo "term-${TERM_SESSION_ID:0:16}"
    else
        echo "pid-$$"
    fi
}

CLAUDE_SESSION_ID="${CLAUDE_SESSION_ID:-$(get_session_id)}"

# Per-session state paths
COORDINATION_DIR="${COORDINATION_DIR:-$HOME/.claude/coordination}"
LABELS_DIR="$COORDINATION_DIR/labels"
STATE_FILE="$LABELS_DIR/${CLAUDE_SESSION_ID}.state"

# Legacy state file for migration
LEGACY_STATE_FILE="${HOME}/.claude/.terminal-label-state"

# Config files (shared across sessions)
USER_CONFIG="${HOME}/.claude/.terminal-label-config"
PROJECT_CONFIG=".claude/.terminal-label-config"
DEFAULT_AWAIT_LABEL="Claude: Awaiting Input..."
DEFAULT_PREFIX="Issue"

# Ensure directories exist
mkdir -p "$LABELS_DIR" 2>/dev/null

# Migrate legacy state file on first use
migrate_legacy_state() {
    if [[ -f "$LEGACY_STATE_FILE" ]] && [[ ! -f "$STATE_FILE" ]]; then
        cp "$LEGACY_STATE_FILE" "$STATE_FILE" 2>/dev/null
    fi
}
migrate_legacy_state

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
set_title() {
    local title="$1"
    # OSC escape sequence for terminal title
    printf '\033]0;%s\007' "$title"
    # Also try tmux if available
    tmux rename-window "$title" 2>/dev/null || true
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
sync_from_session() {
    local session_file="$COORDINATION_DIR/sessions/${CLAUDE_SESSION_ID}.json"
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
            last_beat=$(stat -c %Y "$heartbeat" 2>/dev/null || echo 0)
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
        ;;

    await)
        # Set awaiting label without overwriting saved state
        set_title "$DEFAULT_AWAIT_LABEL"
        ;;

    restore)
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
            echo "No session label found for: $CLAUDE_SESSION_ID"
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
        echo "Session ID: $CLAUDE_SESSION_ID"
        echo "State file: $STATE_FILE"
        echo "User config: $USER_CONFIG"
        echo "Project config: $PROJECT_CONFIG"
        echo ""
        echo "Current prefix: $(get_prefix)"
        echo "Saved label: $(read_label)"
        echo "Saved prefix: $(read_saved_prefix)"
        echo ""

        # Check session registration
        session_file="$COORDINATION_DIR/sessions/${CLAUDE_SESSION_ID}.json"
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
        echo "Session: $CLAUDE_SESSION_ID"
        echo "State:   $STATE_FILE"
        echo ""
        echo "Examples:"
        echo "  $0 issue 42 'Fix login bug'"
        echo "  $0 issue NHL 123 'Player Landing'"
        echo "  $0 project MyApp"
        echo "  $0 prefix Django"
        exit 1
        ;;
esac
