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

# Tiered staleness thresholds (in seconds)
# Designed for real team workflows where issues take hours/days
# - ACTIVE: < 5 min = actively interacting with Claude
# - IDLE: 5 min - 1 hour = stepped away briefly
# - STALE: 1 - 4 hours = gone for extended period, can override
# - ABANDONED: > 24 hours = next day, auto-release
ACTIVE_THRESHOLD=300        # 5 minutes
IDLE_THRESHOLD=3600         # 1 hour
STALE_THRESHOLD=14400       # 4 hours
ABANDONED_THRESHOLD=86400   # 24 hours

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
        ACTIVE_THRESHOLD=$(jq -r '.active_threshold // 300' "$CONFIG_FILE" 2>/dev/null || echo 300)
        IDLE_THRESHOLD=$(jq -r '.idle_threshold // 3600' "$CONFIG_FILE" 2>/dev/null || echo 3600)
        STALE_THRESHOLD=$(jq -r '.stale_threshold // 14400' "$CONFIG_FILE" 2>/dev/null || echo 14400)
        ABANDONED_THRESHOLD=$(jq -r '.abandoned_threshold // 86400' "$CONFIG_FILE" 2>/dev/null || echo 86400)
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
# Uses IDLE_THRESHOLD to consider active/idle sessions as "alive"
is_session_alive() {
    local session_id="$1"
    local heartbeat_file="$HEARTBEAT_DIR/${session_id}.heartbeat"

    if [[ ! -f "$heartbeat_file" ]]; then
        return 1
    fi

    local last_beat=$(stat -c %Y "$heartbeat_file" 2>/dev/null || echo 0)
    local now=$(date +%s)
    local age=$((now - last_beat))

    # Consider alive if active or idle (< 5 minutes)
    [[ $age -lt $IDLE_THRESHOLD ]]
}

# Get tiered session status
# Returns: "active", "idle", "stale", "abandoned", or "dead"
get_session_status() {
    local session_id="$1"
    local heartbeat_file="$HEARTBEAT_DIR/${session_id}.heartbeat"

    if [[ ! -f "$heartbeat_file" ]]; then
        echo "dead"
        return
    fi

    local last_beat=$(stat -c %Y "$heartbeat_file" 2>/dev/null || echo 0)
    local now=$(date +%s)
    local age=$((now - last_beat))

    if [[ $age -lt $ACTIVE_THRESHOLD ]]; then
        echo "active"
    elif [[ $age -lt $IDLE_THRESHOLD ]]; then
        echo "idle"
    elif [[ $age -lt $ABANDONED_THRESHOLD ]]; then
        echo "stale"
    else
        echo "abandoned"
    fi
}

# Get heartbeat age in seconds
get_heartbeat_age() {
    local session_id="$1"
    local heartbeat_file="$HEARTBEAT_DIR/${session_id}.heartbeat"

    if [[ -f "$heartbeat_file" ]]; then
        local last_beat=$(stat -c %Y "$heartbeat_file" 2>/dev/null || echo 0)
        echo $(($(date +%s) - last_beat))
    else
        echo "-1"
    fi
}

# Format age in human-readable form (e.g., "5s", "3m", "1h 5m")
format_age() {
    local age="$1"

    if [[ $age -lt 0 ]]; then
        echo "unknown"
    elif [[ $age -lt 60 ]]; then
        echo "${age}s"
    elif [[ $age -lt 3600 ]]; then
        local mins=$((age / 60))
        local secs=$((age % 60))
        if [[ $secs -gt 0 ]]; then
            echo "${mins}m ${secs}s"
        else
            echo "${mins}m"
        fi
    else
        local hours=$((age / 3600))
        local mins=$(((age % 3600) / 60))
        if [[ $mins -gt 0 ]]; then
            echo "${hours}h ${mins}m"
        else
            echo "${hours}h"
        fi
    fi
}

# Derive label prefix from repo name
# e.g., nhl-api -> NHL, claude-power-pack -> CPP
derive_label_prefix() {
    local repo_name="$1"
    local first_part="${repo_name%%-*}"

    # If first part is 2-4 chars, use it entirely (uppercase)
    if [[ ${#first_part} -le 4 ]] && [[ ${#first_part} -ge 2 ]]; then
        echo "$first_part" | tr '[:lower:]' '[:upper:]'
    else
        # Otherwise take first letter of each hyphen-separated word
        echo "$repo_name" | tr '-' '\n' | awk '{printf toupper(substr($0,1,1))}' | head -c 4
    fi
}

# Get repo owner and name from git remote
get_repo_info() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")

    if [[ "$remote_url" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
        echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]%.git}"
    else
        echo ""
    fi
}

# Find which session has claimed an issue
# Usage: find_issue_claim REPO_OWNER REPO_NAME ISSUE_NUMBER
# Returns: session_id if claimed, empty if available
find_issue_claim() {
    local repo_owner="$1"
    local repo_name="$2"
    local issue_number="$3"

    for session_file in "$SESSION_DIR"/*.json; do
        [[ -f "$session_file" ]] || continue

        local claim_issue=$(jq -r '.claim.issue_number // empty' "$session_file" 2>/dev/null)
        local claim_repo=$(jq -r '.claim.repo_name // empty' "$session_file" 2>/dev/null)
        local claim_owner=$(jq -r '.claim.repo_owner // empty' "$session_file" 2>/dev/null)
        local session_id=$(jq -r '.session_id // empty' "$session_file" 2>/dev/null)

        if [[ "$claim_issue" == "$issue_number" ]] && \
           [[ "$claim_repo" == "$repo_name" ]] && \
           [[ "$claim_owner" == "$repo_owner" ]]; then
            echo "$session_id"
            return 0
        fi
    done

    echo ""
}

# List all claimed issues across active/idle sessions (not stale/abandoned)
# Usage: list_claimed_issues [REPO_OWNER/REPO_NAME]
# Output: JSON array of claimed issues with status tier
list_claimed_issues() {
    local filter_repo="${1:-}"
    local result="[]"

    for session_file in "$SESSION_DIR"/*.json; do
        [[ -f "$session_file" ]] || continue

        local session_id=$(jq -r '.session_id // empty' "$session_file" 2>/dev/null)

        # Get tiered status
        local status=$(get_session_status "$session_id")

        # Skip stale/abandoned/dead sessions for active claims list
        if [[ "$status" == "stale" ]] || [[ "$status" == "abandoned" ]] || [[ "$status" == "dead" ]]; then
            continue
        fi

        local claim=$(jq -c '.claim // empty' "$session_file" 2>/dev/null)
        if [[ -n "$claim" ]] && [[ "$claim" != "null" ]] && [[ "$claim" != "" ]]; then
            local repo_full=$(jq -r '"\(.claim.repo_owner)/\(.claim.repo_name)"' "$session_file" 2>/dev/null)

            # Apply repo filter if provided
            if [[ -z "$filter_repo" ]] || [[ "$repo_full" == "$filter_repo" ]]; then
                local age=$(get_heartbeat_age "$session_id")
                local entry=$(jq -c --arg age "$age" --arg status "$status" '{
                    session_id: .session_id,
                    issue_number: .claim.issue_number,
                    issue_title: .claim.issue_title,
                    repo: "\(.claim.repo_owner)/\(.claim.repo_name)",
                    claimed_at: .claim.claimed_at,
                    heartbeat_age: ($age | tonumber),
                    status: $status
                }' "$session_file" 2>/dev/null)
                result=$(echo "$result" | jq --argjson e "$entry" '. + [$e]')
            fi
        fi
    done

    echo "$result"
}

# Claim an issue for this session
# Usage: claim_issue REPO_OWNER REPO_NAME ISSUE_NUMBER [TITLE] [PREFIX]
claim_issue() {
    local repo_owner="$1"
    local repo_name="$2"
    local issue_number="$3"
    local issue_title="${4:-}"
    local label_prefix="${5:-}"
    local session_file="$SESSION_DIR/${CLAUDE_SESSION_ID}.json"
    local now=$(date -Iseconds)

    # Validate parameters
    if [[ -z "$repo_owner" ]] || [[ -z "$repo_name" ]] || [[ -z "$issue_number" ]]; then
        echo -e "${RED}Error: repo_owner, repo_name, and issue_number required${NC}" >&2
        return 1
    fi

    # Check if issue is already claimed by another session
    local conflict_session=""
    conflict_session=$(find_issue_claim "$repo_owner" "$repo_name" "$issue_number")

    if [[ -n "$conflict_session" ]] && [[ "$conflict_session" != "$CLAUDE_SESSION_ID" ]]; then
        local status=$(get_session_status "$conflict_session")
        local age=$(get_heartbeat_age "$conflict_session")
        local age_str=$(format_age "$age")

        case "$status" in
            active)
                # Fully blocked - actively working
                echo -e "${RED}Error: Issue #${issue_number} is being worked on by session: $conflict_session (active, ${age_str})${NC}" >&2
                return 1
                ;;
            idle)
                # Blocked but warn - session is idle
                echo -e "${RED}Error: Issue #${issue_number} is claimed by idle session: $conflict_session (idle for ${age_str})${NC}" >&2
                echo -e "${YELLOW}Hint: Wait for session to become stale (>5 min) or ask them to release the claim${NC}" >&2
                return 1
                ;;
            stale)
                # Allow override with warning
                echo -e "${YELLOW}Warning: Overriding stale claim from session: $conflict_session (stale for ${age_str})${NC}" >&2
                ;;
            abandoned|dead)
                # Auto-release and continue
                echo -e "${CYAN}Info: Releasing abandoned claim from session: $conflict_session${NC}" >&2
                ;;
        esac
    fi

    # Fetch issue title if not provided
    if [[ -z "$issue_title" ]]; then
        issue_title=$(gh issue view "$issue_number" --repo "${repo_owner}/${repo_name}" --json title --jq '.title' 2>/dev/null | head -c 50)
        issue_title="${issue_title:-Issue $issue_number}"
    fi

    # Determine label prefix
    if [[ -z "$label_prefix" ]]; then
        label_prefix=$(derive_label_prefix "$repo_name")
    fi

    # Build terminal label
    local terminal_label="${label_prefix} #${issue_number}: ${issue_title}"

    # Ensure session file exists
    if [[ ! -f "$session_file" ]]; then
        register_session
    fi

    # Update session with claim
    local tmp=$(mktemp)
    jq --arg now "$now" \
       --arg issue_number "$issue_number" \
       --arg issue_title "$issue_title" \
       --arg repo_owner "$repo_owner" \
       --arg repo_name "$repo_name" \
       --arg prefix "$label_prefix" \
       --arg terminal_label "$terminal_label" \
       --arg source "manual" \
       '.claim = {
          "issue_number": ($issue_number | tonumber),
          "issue_title": $issue_title,
          "repo_owner": $repo_owner,
          "repo_name": $repo_name,
          "claimed_at": $now,
          "source": $source,
          "label_prefix": $prefix
        } | .issue = ($issue_number | tonumber) | .terminal_label = $terminal_label' \
       "$session_file" > "$tmp"
    mv "$tmp" "$session_file"

    echo -e "${GREEN}Claimed issue #${issue_number}:${NC} ${issue_title}"
    echo "$terminal_label"
}

# Release the current session's issue claim
release_claim() {
    local session_file="$SESSION_DIR/${CLAUDE_SESSION_ID}.json"

    if [[ ! -f "$session_file" ]]; then
        echo -e "${YELLOW}No session registered${NC}"
        return 0
    fi

    local current_claim=$(jq -r '.claim.issue_number // empty' "$session_file" 2>/dev/null)

    if [[ -z "$current_claim" ]]; then
        echo -e "${YELLOW}No issue claimed${NC}"
        return 0
    fi

    # Clear claim and terminal_label
    local tmp=$(mktemp)
    jq '.claim = null | .terminal_label = null' "$session_file" > "$tmp"
    mv "$tmp" "$session_file"

    echo -e "${GREEN}Released claim on issue #${current_claim}${NC}"
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
    local label_file="$COORDINATION_DIR/labels/${CLAUDE_SESSION_ID}.state"

    # Log claim release if any
    if [[ -f "$session_file" ]]; then
        local claimed_issue=$(jq -r '.claim.issue_number // empty' "$session_file" 2>/dev/null)
        if [[ -n "$claimed_issue" ]]; then
            echo -e "${YELLOW}Released claim:${NC} Issue #$claimed_issue"
        fi
    fi

    # Release any locks held by this session
    for lock_file in "$LOCK_DIR"/*.lock; do
        [[ -f "$lock_file" ]] || continue
        local holder=$(jq -r '.session_id // ""' "$lock_file" 2>/dev/null)
        if [[ "$holder" == "$CLAUDE_SESSION_ID" ]]; then
            local lock_name=$(basename "$lock_file" .lock)
            rm -f "$lock_file"
            echo -e "${YELLOW}Released lock:${NC} $lock_name"
        fi
    done

    # Remove session files (including per-session label state)
    rm -f "$session_file" "$heartbeat_file" "$label_file"
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
    for session_file in "$SESSION_DIR"/*.json; do
        [[ -f "$session_file" ]] || continue
        found=1

        local session_id=$(jq -r '.session_id // "unknown"' "$session_file")
        local cwd=$(jq -r '.cwd // "unknown"' "$session_file")
        local status=$(jq -r '.status // "unknown"' "$session_file")
        local issue=$(jq -r '.issue // "none"' "$session_file")
        local started_at=$(jq -r '.started_at // "unknown"' "$session_file")
        local claim_issue=$(jq -r '.claim.issue_number // empty' "$session_file")
        local claim_title=$(jq -r '.claim.issue_title // empty' "$session_file")
        local terminal_label=$(jq -r '.terminal_label // empty' "$session_file")

        # Get tiered status with appropriate color
        local session_status=$(get_session_status "$session_id")
        local status_display=""
        case "$session_status" in
            active)
                status_display="${GREEN}(active)${NC}"
                ;;
            idle)
                status_display="${YELLOW}(idle)${NC}"
                ;;
            stale)
                status_display="${RED}(stale)${NC}"
                ;;
            abandoned)
                status_display="${RED}(abandoned)${NC}"
                ;;
            *)
                status_display="${RED}(dead)${NC}"
                ;;
        esac

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

        echo -e "${prefix}${BLUE}$session_id${NC} $status_display"
        echo -e "    Status: $status"
        if [[ -n "$claim_issue" ]]; then
            echo -e "    Claimed: ${GREEN}#${claim_issue}${NC} - ${claim_title}"
            if [[ -n "$terminal_label" ]]; then
                echo -e "    Label: ${terminal_label}"
            fi
        elif [[ "$issue" != "none" ]] && [[ "$issue" != "null" ]]; then
            echo -e "    Issue: #$issue (from path, not claimed)"
        fi
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
    for lock_file in "$LOCK_DIR"/*.lock; do
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
    for session_file in "$SESSION_DIR"/*.json; do
        [[ -f "$session_file" ]] || continue

        local session_id=$(jq -r '.session_id // ""' "$session_file")
        if [[ -z "$session_id" ]]; then
            continue
        fi

        if ! is_session_alive "$session_id"; then
            # Release locks held by this session
            for lock_file in "$LOCK_DIR"/*.lock; do
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
Usage: session-register.sh COMMAND [ARGS]

Session Commands:
  start                              Register new session (SessionStart hook)
  pause                              Mark session as paused (Stop hook)
  end                                End session and release all locks/claims
  status                             Show all registered sessions and state
  cleanup                            Remove stale sessions and their locks

Issue Claiming Commands:
  claim OWNER/REPO NUM [TITLE] [PREFIX]   Claim an issue for this session
  release-claim                           Release the current claim
  list-claims [OWNER/REPO]                List all active issue claims (JSON)
  find-claim OWNER REPO NUM               Find which session claimed an issue

Environment Variables:
  CLAUDE_SESSION_ID  Session identifier (auto-generated if not set)
  COORDINATION_DIR   Override default ~/.claude/coordination

Hook Integration:
  - SessionStart -> session-register.sh start
  - Stop         -> session-register.sh pause

Examples:
  # View all sessions
  session-register.sh status

  # Claim issue #167 in cooneycw/NHL-API
  session-register.sh claim cooneycw/NHL-API 167 "Player Landing" NHL

  # List all active claims
  session-register.sh list-claims

  # List claims for a specific repo
  session-register.sh list-claims cooneycw/NHL-API

  # Release current claim
  session-register.sh release-claim

  # Check if issue is claimed
  session-register.sh find-claim cooneycw NHL-API 167
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
        claim)
            # claim OWNER/REPO NUM [TITLE] [PREFIX]
            # Note: repo_spec can come from $2 or REPO_INFO env var
            # This handles the common pattern: REPO_INFO="owner/repo" script claim "$REPO_INFO" ...
            # where $REPO_INFO expands empty due to shell evaluation order
            local repo_spec="${2:-}"
            local issue_num="${3:-}"
            local title="${4:-}"
            local prefix="${5:-}"

            # Fallback to REPO_INFO env var if repo_spec is empty
            if [[ -z "$repo_spec" ]] && [[ -n "${REPO_INFO:-}" ]]; then
                repo_spec="$REPO_INFO"
            fi

            if [[ -z "$repo_spec" ]] || [[ -z "$issue_num" ]]; then
                echo -e "${RED}Usage: session-register.sh claim OWNER/REPO ISSUE_NUM [TITLE] [PREFIX]${NC}" >&2
                echo -e "${YELLOW}Hint: Set REPO_INFO env var or pass repo as first argument${NC}" >&2
                exit 1
            fi

            local repo_owner="${repo_spec%%/*}"
            local repo_name="${repo_spec##*/}"
            claim_issue "$repo_owner" "$repo_name" "$issue_num" "$title" "$prefix"
            ;;
        release-claim)
            release_claim
            ;;
        list-claims)
            list_claimed_issues "${2:-}"
            ;;
        find-claim)
            # find-claim OWNER REPO NUM
            if [[ -z "${2:-}" ]] || [[ -z "${3:-}" ]] || [[ -z "${4:-}" ]]; then
                echo -e "${RED}Usage: session-register.sh find-claim OWNER REPO ISSUE_NUM${NC}" >&2
                exit 1
            fi
            find_issue_claim "$2" "$3" "$4"
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
