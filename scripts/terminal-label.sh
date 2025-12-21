#!/bin/bash
# Terminal label management for Claude Code sessions
# Generic version - works with any project
#
# Usage:
#   terminal-label.sh set "Label Text"           - Set label and save to state
#   terminal-label.sh await                      - Set to "awaiting" mode (no save)
#   terminal-label.sh restore                    - Restore from saved state
#   terminal-label.sh issue [PREFIX] NUM [TITLE] - Set issue-specific label
#   terminal-label.sh project [PREFIX]           - Set project label (awaiting selection)
#   terminal-label.sh prefix [VALUE]             - Get/set default prefix
#   terminal-label.sh status                     - Show current configuration
#
# Configuration (priority order):
#   1. TERMINAL_LABEL_PREFIX env var
#   2. .claude/.terminal-label-config (project-level)
#   3. ~/.claude/.terminal-label-config (user-level)
#   4. Default: "Issue"
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

STATE_FILE="${HOME}/.claude/.terminal-label-state"
USER_CONFIG="${HOME}/.claude/.terminal-label-config"
PROJECT_CONFIG=".claude/.terminal-label-config"
DEFAULT_AWAIT_LABEL="Claude: Awaiting Input..."
DEFAULT_PREFIX="Issue"

# Ensure state directory exists
mkdir -p "$(dirname "$STATE_FILE")" 2>/dev/null

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
        saved=$(read_label)
        if [[ -n "$saved" ]]; then
            set_title "$saved"
        fi
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
        echo "State file: $STATE_FILE"
        echo "User config: $USER_CONFIG"
        echo "Project config: $PROJECT_CONFIG"
        echo ""
        echo "Current prefix: $(get_prefix)"
        echo "Saved label: $(read_label)"
        echo "Saved prefix: $(read_saved_prefix)"
        echo ""
        if [[ -n "$TERMINAL_LABEL_PREFIX" ]]; then
            echo "TERMINAL_LABEL_PREFIX env var: $TERMINAL_LABEL_PREFIX"
        fi
        ;;

    *)
        echo "Terminal Label Manager for Claude Code"
        echo ""
        echo "Usage: $0 <command> [args...]"
        echo ""
        echo "Commands:"
        echo "  set <label>              Set terminal title and save"
        echo "  await                    Set to 'awaiting input' mode"
        echo "  restore                  Restore saved label"
        echo "  issue [PREFIX] NUM [TITLE]  Set issue-specific label"
        echo "  project [PREFIX]         Set project label"
        echo "  prefix [VALUE]           Get/set default prefix"
        echo "  status                   Show current configuration"
        echo ""
        echo "Examples:"
        echo "  $0 issue 42 'Fix login bug'"
        echo "  $0 issue NHL 123 'Player Landing'"
        echo "  $0 project MyApp"
        echo "  $0 prefix Django"
        exit 1
        ;;
esac
