#!/bin/bash
#
# pytest-locked.sh - pytest wrapper with session coordination
#
# Acquires a lock before running pytest to prevent test interference
# between concurrent Claude Code sessions in different worktrees.
#
# Usage:
#   pytest-locked.sh [pytest args...]
#
# Examples:
#   pytest-locked.sh -m unit --no-cov
#   pytest-locked.sh tests/unit/ -v
#   pytest-locked.sh -x --tb=short
#
# The lock name is derived from the repository name:
#   pytest-{repo-name}
#
# Environment:
#   PYTEST_LOCK_TIMEOUT  - Lock timeout in seconds (default: 300)
#   COORDINATION_DIR     - Override default ~/.claude/coordination
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK_SCRIPT="$SCRIPT_DIR/session-lock.sh"

# Fallback to PATH if not in same directory
if [[ ! -x "$LOCK_SCRIPT" ]]; then
    LOCK_SCRIPT="session-lock.sh"
fi

# Default timeout (5 minutes)
PYTEST_LOCK_TIMEOUT="${PYTEST_LOCK_TIMEOUT:-300}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get repository name from git
get_repo_name() {
    local git_root
    git_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
        echo "unknown"
        return
    }
    basename "$git_root"
}

# Main
main() {
    local repo_name
    repo_name=$(get_repo_name)
    local lock_name="pytest-${repo_name}"

    echo -e "${BLUE}[pytest-locked]${NC} Acquiring lock: $lock_name (timeout: ${PYTEST_LOCK_TIMEOUT}s)"

    # Acquire lock
    if ! "$LOCK_SCRIPT" acquire "$lock_name" "$PYTEST_LOCK_TIMEOUT"; then
        echo -e "${RED}[pytest-locked]${NC} Failed to acquire lock - another session is running tests"
        echo ""
        echo "To check who holds the lock:"
        echo "  $LOCK_SCRIPT info $lock_name"
        echo ""
        echo "To force release (use with caution):"
        echo "  $LOCK_SCRIPT force-release $lock_name"
        exit 1
    fi

    echo -e "${GREEN}[pytest-locked]${NC} Lock acquired, running pytest..."
    echo ""

    # Run pytest and capture exit code
    local pytest_exit=0
    pytest "$@" || pytest_exit=$?

    echo ""

    # Release lock
    "$LOCK_SCRIPT" release "$lock_name"

    # Report result
    if [[ $pytest_exit -eq 0 ]]; then
        echo -e "${GREEN}[pytest-locked]${NC} Tests passed, lock released"
    else
        echo -e "${YELLOW}[pytest-locked]${NC} Tests failed (exit code: $pytest_exit), lock released"
    fi

    exit $pytest_exit
}

# Handle Ctrl+C gracefully
cleanup() {
    local repo_name
    repo_name=$(get_repo_name)
    local lock_name="pytest-${repo_name}"

    echo ""
    echo -e "${YELLOW}[pytest-locked]${NC} Interrupted, releasing lock..."
    "$LOCK_SCRIPT" release "$lock_name" 2>/dev/null || true
    exit 130
}

trap cleanup INT TERM

main "$@"
