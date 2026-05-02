#!/usr/bin/env bash
# bootstrap-check.sh - Check admin-only bootstrap dependencies before deploy
# Part of Claude Power Pack (CPP)
#
# Thin wrapper that invokes the Python bootstrap checker. Projects declare
# dependencies in .claude/bootstrap.yaml; each dependency has a check_command
# that must exit 0 for the deploy to proceed.
#
# Usage:
#   bootstrap-check.sh              # Check all dependencies
#   bootstrap-check.sh --list       # List configured dependencies
#   bootstrap-check.sh --help       # Show help
#
# Exit codes:
#   0 - All satisfied (or no config present)
#   1 - One or more prerequisites not satisfied
#   2 - Usage error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    cat <<'EOF'
bootstrap-check.sh - Check admin-only bootstrap dependencies

Usage:
  bootstrap-check.sh              Check all bootstrap prerequisites
  bootstrap-check.sh --list       List configured dependencies
  bootstrap-check.sh --help       Show this help

Config file: .claude/bootstrap.yaml

Dependencies define a check_command (exits 0 when satisfied) and a
remediation message shown when the check fails.

Exit codes:
  0 - All satisfied (or no bootstrap.yaml present)
  1 - One or more prerequisites not satisfied
  2 - Usage error
EOF
}

case "${1:-}" in
    --help|-h)
        usage
        exit 0
        ;;
    --list)
        PYTHONPATH="${REPO_ROOT}/lib:${PYTHONPATH:-}" \
            python3 -m lib.cicd.bootstrap list --project-root "$REPO_ROOT"
        exit $?
        ;;
    ""|--check)
        PYTHONPATH="${REPO_ROOT}/lib:${PYTHONPATH:-}" \
            python3 -m lib.cicd.bootstrap check --project-root "$REPO_ROOT"
        exit $?
        ;;
    *)
        echo "Unknown option: $1"
        usage
        exit 2
        ;;
esac
