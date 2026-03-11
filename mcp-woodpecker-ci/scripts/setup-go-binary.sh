#!/bin/bash
# Setup the Woodpecker CI MCP server (Go binary)
# Installs the binary, fetches credentials from AWS Secrets Manager,
# and registers with Claude Code.
#
# Prerequisites:
#   - Go 1.24+ installed
#   - AWS credentials configured (for Secrets Manager access)
#   - Claude Code installed
#
# Usage:
#   ./scripts/setup-go-binary.sh [--secret-name NAME] [--region REGION]

set -euo pipefail

SECRET_NAME="${1:-essent-ai}"
AWS_REGION="${2:-us-east-1}"

echo "=== Woodpecker CI MCP Server Setup ==="
echo ""

# Step 1: Check Go
if ! command -v go &>/dev/null; then
    # Check common install locations
    if [ -x /usr/local/go/bin/go ]; then
        export PATH="/usr/local/go/bin:$PATH"
    else
        echo "ERROR: Go not found. Install from https://go.dev/dl/" >&2
        exit 1
    fi
fi
echo "Go: $(go version)"

# Step 2: Install binary
echo "Installing woodpecker-mcp..."
go install github.com/denysvitali/woodpecker-ci-mcp/cmd/woodpecker-mcp@latest
BINARY="$HOME/go/bin/woodpecker-mcp"

if [ ! -x "$BINARY" ]; then
    echo "ERROR: Binary not found at $BINARY" >&2
    exit 1
fi
echo "Binary: $BINARY"

# Step 3: Configure from AWS Secrets Manager
echo "Fetching credentials from AWS Secrets Manager (secret: $SECRET_NAME, region: $AWS_REGION)..."

CONFIG_DIR="$HOME/.config/woodpecker-mcp"
mkdir -p "$CONFIG_DIR"

python3 -c "
import boto3, json, yaml
from pathlib import Path

client = boto3.client('secretsmanager', region_name='$AWS_REGION')
secret = json.loads(client.get_secret_value(SecretId='$SECRET_NAME')['SecretString'])

url = secret.get('WOODPECKER_HOST', '')
token = secret.get('WOODPECKER_API_TOKEN', '')

if not url or not token:
    raise SystemExit('WOODPECKER_HOST or WOODPECKER_API_TOKEN not found in secret')

config = {'woodpecker': {'url': url, 'token': token}}
config_path = Path('$CONFIG_DIR/config.yaml')
config_path.write_text(yaml.dump(config, default_flow_style=False))
config_path.chmod(0o600)
print(f'Config written to {config_path}')
"

# Step 4: Test connection
echo "Testing connection..."
"$BINARY" test

# Step 5: Register with Claude Code
echo ""
echo "To register with Claude Code, add to your .mcp.json:"
echo ""
echo '  "woodpecker-ci": {'
echo '    "type": "stdio",'
echo "    \"command\": \"$BINARY\","
echo '    "args": ["serve"]'
echo '  }'
echo ""
echo "Or run:"
echo "  claude mcp add --transport stdio -s user woodpecker-ci -- $BINARY serve"
echo ""
echo "=== Setup complete ==="
