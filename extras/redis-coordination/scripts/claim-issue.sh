#!/bin/bash
#
# claim-issue.sh - Quick wrapper for issue claiming
#
# Simplified interface for claiming GitHub issues in Claude Code sessions.
# Wraps session-register.sh claim functions with auto-detection.
#
# Usage:
#   claim-issue.sh NUM [TITLE]       # Claim issue (auto-detect repo)
#   claim-issue.sh --release         # Release current claim
#   claim-issue.sh --list            # Show all active claims
#   claim-issue.sh --check NUM       # Check if issue is available
#   claim-issue.sh --status          # Show current session's claim
#
# Examples:
#   claim-issue.sh 167 "Player Landing Page"
#   claim-issue.sh --check 167
#   claim-issue.sh --release
#

set -euo pipefail

# Find the session-register.sh script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_REGISTER="$SCRIPT_DIR/session-register.sh"

if [[ ! -x "$SESSION_REGISTER" ]]; then
    echo "Error: session-register.sh not found at $SESSION_REGISTER" >&2
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Get repo info from git
get_repo_info() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")

    if [[ "$remote_url" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
        echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]%.git}"
    else
        echo ""
    fi
}

# Print usage
usage() {
    cat << 'EOF'
claim-issue.sh - Quick wrapper for issue claiming

Usage:
  claim-issue.sh NUM [TITLE]       Claim issue (auto-detect repo from git)
  claim-issue.sh --release         Release current session's claim
  claim-issue.sh --list            Show all active claims
  claim-issue.sh --check NUM       Check if issue is available
  claim-issue.sh --status          Show current session's claim

Examples:
  claim-issue.sh 167 "Player Landing Page"
  claim-issue.sh --check 167
  claim-issue.sh --release

The repo owner/name is auto-detected from 'git remote get-url origin'.
EOF
}

# Main command handling
case "${1:-}" in
    --release|-r)
        "$SESSION_REGISTER" release-claim
        ;;

    --list|-l)
        repo_info=$(get_repo_info)
        if [[ -n "$repo_info" ]]; then
            echo -e "${CYAN}Active claims for $repo_info:${NC}"
            "$SESSION_REGISTER" list-claims "$repo_info"
        else
            echo -e "${CYAN}All active claims:${NC}"
            "$SESSION_REGISTER" list-claims
        fi
        ;;

    --check|-c)
        if [[ -z "${2:-}" ]]; then
            echo "Error: --check requires issue number" >&2
            exit 1
        fi

        repo_info=$(get_repo_info)
        if [[ -z "$repo_info" ]]; then
            echo "Error: Could not detect repo from git remote" >&2
            exit 1
        fi

        owner="${repo_info%%/*}"
        name="${repo_info##*/}"

        result=$("$SESSION_REGISTER" find-claim "$owner" "$name" "$2")
        if [[ -n "$result" ]]; then
            echo -e "${YELLOW}Issue #$2 is claimed by session:${NC} $result"
            exit 1
        else
            echo -e "${GREEN}Issue #$2 is available${NC}"
            exit 0
        fi
        ;;

    --status|-s)
        "$SESSION_REGISTER" status | grep -A 20 "claim\|terminal_label" || echo "No active claim"
        ;;

    --help|-h)
        usage
        ;;

    "")
        usage
        exit 1
        ;;

    -*)
        echo "Error: Unknown option: $1" >&2
        usage
        exit 1
        ;;

    *)
        # Claim an issue: claim-issue.sh NUM [TITLE]
        issue_num="$1"
        title="${2:-}"

        # Validate issue number
        if ! [[ "$issue_num" =~ ^[0-9]+$ ]]; then
            echo "Error: Issue number must be numeric: $issue_num" >&2
            exit 1
        fi

        repo_info=$(get_repo_info)
        if [[ -z "$repo_info" ]]; then
            echo "Error: Could not detect repo from git remote" >&2
            echo "Make sure you're in a git repository with a GitHub remote" >&2
            exit 1
        fi

        # Call session-register.sh claim
        "$SESSION_REGISTER" claim "$repo_info" "$issue_num" "$title"
        ;;
esac
