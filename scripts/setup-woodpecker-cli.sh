#!/bin/bash
# Setup the Woodpecker CLI and configure authentication.
# Installs the CLI (if missing), fetches credentials from AWS Secrets Manager,
# and creates a woodpecker-cli context for the default server.
#
# Prerequisites:
#   - AWS credentials configured (for Secrets Manager access)
#   - Python 3.11+ with boto3 available (or uv)
#
# Usage:
#   ./scripts/setup-woodpecker-cli.sh [--secret-name NAME] [--region REGION]

set -euo pipefail

SECRET_NAME="essent-ai"
AWS_REGION="us-east-1"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --secret-name) SECRET_NAME="$2"; shift 2 ;;
        --region) AWS_REGION="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

echo "=== Woodpecker CLI Setup ==="
echo ""

# Step 1: Check if woodpecker-cli is installed
if command -v woodpecker-cli &>/dev/null; then
    echo "Woodpecker CLI: $(woodpecker-cli --version)"
else
    echo "Woodpecker CLI not found. Installing..."

    # Detect architecture
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  ARCH="amd64" ;;
        aarch64) ARCH="arm64" ;;
        *) echo "ERROR: Unsupported architecture: $ARCH" >&2; exit 1 ;;
    esac

    OS=$(uname -s | tr '[:upper:]' '[:lower:]')

    # Fetch latest release tag from GitHub
    LATEST=$(curl -s https://api.github.com/repos/woodpecker-ci/woodpecker/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
    if [[ -z "$LATEST" ]]; then
        echo "ERROR: Could not determine latest Woodpecker CLI version" >&2
        exit 1
    fi

    DOWNLOAD_URL="https://github.com/woodpecker-ci/woodpecker/releases/download/v${LATEST}/woodpecker-cli_${OS}_${ARCH}.tar.gz"
    echo "Downloading woodpecker-cli v${LATEST} for ${OS}/${ARCH}..."

    TMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TMP_DIR"' EXIT

    curl -fsSL "$DOWNLOAD_URL" -o "$TMP_DIR/woodpecker-cli.tar.gz"
    tar -xzf "$TMP_DIR/woodpecker-cli.tar.gz" -C "$TMP_DIR"

    if [[ -f "$TMP_DIR/woodpecker-cli" ]]; then
        sudo install -m 755 "$TMP_DIR/woodpecker-cli" /usr/local/bin/woodpecker-cli
        echo "Installed: $(woodpecker-cli --version)"
    else
        echo "ERROR: woodpecker-cli binary not found in archive" >&2
        exit 1
    fi
fi

# Step 2: Fetch credentials from AWS Secrets Manager
echo ""
echo "Fetching credentials from AWS Secrets Manager (secret: $SECRET_NAME, region: $AWS_REGION)..."

# Try python3 directly, then fall back to uv
PYTHON_CMD="python3"
if ! $PYTHON_CMD -c "import boto3" 2>/dev/null; then
    if command -v uv &>/dev/null; then
        PYTHON_CMD="uv run python3"
        uv pip install boto3 --quiet 2>/dev/null || true
    else
        echo "ERROR: boto3 not available. Install with: pip install boto3" >&2
        exit 1
    fi
fi

CREDS=$($PYTHON_CMD -c "
import boto3, json
client = boto3.client('secretsmanager', region_name='$AWS_REGION')
resp = client.get_secret_value(SecretId='$SECRET_NAME')
secrets = json.loads(resp['SecretString'])
host = secrets.get('WOODPECKER_HOST', '')
token = secrets.get('WOODPECKER_API_TOKEN', '')
if not host or not token:
    raise SystemExit('WOODPECKER_HOST or WOODPECKER_API_TOKEN not found in secret')
print(f'{host}\n{token}')
")

WP_SERVER=$(echo "$CREDS" | sed -n '1p')
WP_TOKEN=$(echo "$CREDS" | sed -n '2p')

echo "Server: $WP_SERVER"
echo "Token: ****$(echo "$WP_TOKEN" | tail -c 5)"

# Step 3: Configure woodpecker-cli context
echo ""
echo "Configuring woodpecker-cli context..."
woodpecker-cli setup --server "$WP_SERVER" --token "$WP_TOKEN" --context default

# Step 4: Verify connectivity
echo ""
echo "Verifying connectivity..."
if woodpecker-cli repo ls 2>&1 | head -5; then
    echo ""
    echo "=== Setup complete ==="
    echo "Woodpecker CLI is configured and can reach the server."
    echo "Run 'woodpecker-cli repo ls' to list repositories."
else
    echo ""
    echo "WARNING: Could not list repositories. Check your token permissions."
    exit 1
fi
