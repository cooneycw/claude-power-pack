#!/bin/bash
#
# secrets-get.sh - Get credentials using Python secrets module
#
# Bash wrapper that calls the Python lib/secrets module.
# Outputs masked credential information (never exposes real secrets).
#
# Usage:
#   secrets-get.sh                    # Get default DB credentials
#   secrets-get.sh database           # Get database credentials
#   secrets-get.sh --secret-id myapp  # Get custom secret
#   secrets-get.sh --provider aws     # Force AWS provider
#   secrets-get.sh --json             # Output as JSON (masked)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")/lib"

# Default values
SECRET_ID="DB"
PROVIDER=""
OUTPUT_FORMAT="text"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --secret-id|-s)
            SECRET_ID="$2"
            shift 2
            ;;
        --provider|-p)
            PROVIDER="$2"
            shift 2
            ;;
        --json|-j)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --help|-h)
            cat << 'EOF'
secrets-get.sh - Get credentials using Python secrets module

USAGE:
    secrets-get.sh [OPTIONS] [SECRET_ID]

OPTIONS:
    --secret-id, -s ID    Secret identifier (default: DB)
    --provider, -p NAME   Force provider: aws, env (default: auto)
    --json, -j            Output as JSON (masked)
    --help, -h            Show this help

EXAMPLES:
    # Get database credentials (auto-detect provider)
    secrets-get.sh

    # Get specific secret from AWS
    secrets-get.sh --provider aws --secret-id prod/database

    # Get credentials as JSON
    secrets-get.sh --json

ENVIRONMENT:
    DB_HOST, DB_USER, DB_PASSWORD, DB_NAME - For env provider
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY - For AWS provider

NOTE:
    This script NEVER outputs actual secret values.
    All passwords and tokens are masked as ****.
EOF
            exit 0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            SECRET_ID="$1"
            shift
            ;;
    esac
done

# Python script to get credentials
PYTHON_SCRIPT=$(cat << 'PYEOF'
import sys
import json
import os

# Add lib to path
lib_dir = os.environ.get('LIB_DIR', '')
if lib_dir:
    sys.path.insert(0, lib_dir)

try:
    from secrets import get_credentials, get_provider
    from secrets.providers import EnvSecretsProvider, AWSSecretsProvider
except ImportError as e:
    print(f"Error: Could not import secrets module: {e}", file=sys.stderr)
    print("Ensure PYTHONPATH includes the lib directory", file=sys.stderr)
    sys.exit(1)

secret_id = os.environ.get('SECRET_ID', 'DB')
provider_name = os.environ.get('PROVIDER', '')
output_format = os.environ.get('OUTPUT_FORMAT', 'text')

# Select provider
if provider_name == 'aws':
    provider = AWSSecretsProvider()
    if not provider.is_available():
        print("Error: AWS Secrets Manager not available", file=sys.stderr)
        sys.exit(1)
elif provider_name == 'env':
    provider = EnvSecretsProvider()
else:
    provider = get_provider()

try:
    creds = get_credentials(secret_id, provider=provider)

    if output_format == 'json':
        print(json.dumps(creds.dsn_masked, indent=2))
    else:
        print(f"Provider: {provider.name}")
        print(f"Secret ID: {secret_id}")
        print(f"")
        print(f"Host: {creds.host}")
        print(f"Port: {creds.port}")
        print(f"Database: {creds.database}")
        print(f"Username: {creds.username}")
        print(f"Password: ****")
        print(f"")
        print(f"Connection String: {creds.connection_string}")

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
)

# Run Python script with environment
LIB_DIR="$LIB_DIR" \
SECRET_ID="$SECRET_ID" \
PROVIDER="$PROVIDER" \
OUTPUT_FORMAT="$OUTPUT_FORMAT" \
python3 -c "$PYTHON_SCRIPT"
