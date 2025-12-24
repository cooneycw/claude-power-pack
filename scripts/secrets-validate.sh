#!/bin/bash
#
# secrets-validate.sh - Validate credentials without exposing them
#
# Tests that credentials are configured and accessible.
# Never displays actual secret values.
#
# Usage:
#   secrets-validate.sh              # Validate all providers
#   secrets-validate.sh --db         # Test database connection
#   secrets-validate.sh --aws        # Test AWS access
#   secrets-validate.sh --env        # Test environment variables
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")/lib"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    local status="$1"
    local message="$2"

    case "$status" in
        ok)
            echo -e "${GREEN}✓${NC} $message"
            ;;
        warn)
            echo -e "${YELLOW}!${NC} $message"
            ;;
        fail)
            echo -e "${RED}✗${NC} $message"
            ;;
        info)
            echo -e "${BLUE}ℹ${NC} $message"
            ;;
        *)
            echo "  $message"
            ;;
    esac
}

validate_env() {
    echo "=== Environment Variables ==="
    echo ""

    local found=0

    # Check for common database env vars
    if [[ -n "${DB_HOST:-}" ]]; then
        print_status ok "DB_HOST is set: ${DB_HOST}"
        found=1
    fi

    if [[ -n "${DB_USER:-}" ]]; then
        print_status ok "DB_USER is set: ${DB_USER}"
    fi

    if [[ -n "${DB_PASSWORD:-}" ]]; then
        print_status ok "DB_PASSWORD is set: ****"
    else
        print_status warn "DB_PASSWORD is not set"
    fi

    if [[ -n "${DB_NAME:-}" ]]; then
        print_status ok "DB_NAME is set: ${DB_NAME}"
    fi

    if [[ -f ".env" ]]; then
        print_status ok ".env file exists"
    else
        print_status warn ".env file not found (optional)"
    fi

    echo ""
    return 0
}

validate_aws() {
    echo "=== AWS Credentials ==="
    echo ""

    # Check for AWS env vars
    if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
        # Show first 4 chars only
        local key_prefix="${AWS_ACCESS_KEY_ID:0:4}"
        print_status ok "AWS_ACCESS_KEY_ID is set: ${key_prefix}..."
    else
        print_status warn "AWS_ACCESS_KEY_ID not set"
    fi

    if [[ -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        print_status ok "AWS_SECRET_ACCESS_KEY is set: ****"
    else
        print_status warn "AWS_SECRET_ACCESS_KEY not set"
    fi

    if [[ -n "${AWS_DEFAULT_REGION:-}" ]]; then
        print_status ok "AWS_DEFAULT_REGION: ${AWS_DEFAULT_REGION}"
    else
        print_status info "AWS_DEFAULT_REGION not set (defaults to us-east-1)"
    fi

    # Try to validate AWS credentials
    if command -v aws &>/dev/null; then
        if aws sts get-caller-identity &>/dev/null; then
            local identity
            identity=$(aws sts get-caller-identity --query 'Arn' --output text 2>/dev/null || echo "unknown")
            print_status ok "AWS credentials valid: $identity"
        else
            print_status fail "AWS credentials invalid or expired"
        fi
    else
        print_status warn "AWS CLI not installed (cannot validate credentials)"
    fi

    echo ""
    return 0
}

validate_db() {
    echo "=== Database Connection ==="
    echo ""

    # Use Python to test database connection
    local result
    result=$(python3 << 'PYEOF' 2>&1) || true
import sys
import os

lib_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.environ.get('LIB_DIR', lib_dir + '/lib'))

try:
    from secrets import get_credentials
    creds = get_credentials()
    print(f"OK|Credentials loaded: {creds.connection_string}")
except Exception as e:
    print(f"FAIL|{e}")
PYEOF

    if [[ "$result" == OK* ]]; then
        local msg="${result#OK|}"
        print_status ok "$msg"

        # Try actual connection if psql is available
        if command -v psql &>/dev/null; then
            # Get credentials silently
            local host="${DB_HOST:-localhost}"
            local port="${DB_PORT:-5432}"
            local dbname="${DB_NAME:-}"
            local user="${DB_USER:-}"

            if [[ -n "$dbname" && -n "$user" ]]; then
                if PGPASSWORD="${DB_PASSWORD:-}" psql -h "$host" -p "$port" -U "$user" -d "$dbname" -c "SELECT 1" &>/dev/null; then
                    print_status ok "Database connection successful"
                else
                    print_status fail "Database connection failed"
                fi
            fi
        else
            print_status info "psql not installed (cannot test connection)"
        fi
    else
        local msg="${result#FAIL|}"
        print_status fail "Failed to load credentials: $msg"
    fi

    echo ""
    return 0
}

# Main
case "${1:-}" in
    --env)
        validate_env
        ;;
    --aws)
        validate_aws
        ;;
    --db)
        LIB_DIR="$LIB_DIR" validate_db
        ;;
    --all|"")
        validate_env
        validate_aws
        LIB_DIR="$LIB_DIR" validate_db

        echo "=== Summary ==="
        echo "Run with --db, --aws, or --env for specific validation"
        ;;
    --help|-h)
        cat << 'EOF'
secrets-validate.sh - Validate credentials without exposing them

USAGE:
    secrets-validate.sh              Validate all providers
    secrets-validate.sh --env        Validate environment variables
    secrets-validate.sh --aws        Validate AWS credentials
    secrets-validate.sh --db         Test database connection
    secrets-validate.sh --help       Show this help

CHECKS PERFORMED:
    --env: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, .env file
    --aws: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, sts:GetCallerIdentity
    --db:  Load credentials, test PostgreSQL connection (if psql available)

TROUBLESHOOTING:
    "Could not import secrets module"
        → Ensure PYTHONPATH includes lib directory:
          export PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"

    "AWS credentials invalid or expired"
        → Run: aws configure
        → Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

    "Database connection failed"
        → Verify DB_HOST, DB_USER, DB_PASSWORD, DB_NAME are set
        → Check if database server is running
        → Verify network connectivity: nc -zv $DB_HOST $DB_PORT

    "psql not installed"
        → Install: sudo apt install postgresql-client

NOTE:
    This script NEVER displays actual secret values.
    Passwords are always shown as ****.
EOF
        exit 0
        ;;
    *)
        echo "Unknown option: $1" >&2
        echo "Run 'secrets-validate.sh --help' for usage" >&2
        exit 1
        ;;
esac
