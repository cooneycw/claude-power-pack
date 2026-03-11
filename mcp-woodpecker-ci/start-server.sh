#!/bin/bash
# Start the MCP Woodpecker CI Server
# This script uses uv to manage dependencies and run the server

set -euo pipefail

# Change to the server directory
cd "$(dirname "$0")"

# Pre-flight: check uv is available
if ! command -v uv &>/dev/null; then
    echo "ERROR: 'uv' not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# Pre-flight: check Woodpecker credentials
if [[ -z "${WOODPECKER_URL:-}" ]] && [[ -z "${WOODPECKER_API_TOKEN:-}" ]] && [[ -z "${AWS_SECRET_NAME:-}" ]]; then
    echo "WARNING: No Woodpecker credentials detected." >&2
    echo "  Set WOODPECKER_URL and WOODPECKER_API_TOKEN, or" >&2
    echo "  set AWS_SECRET_NAME (default: essent-ai) for auto-fetch from AWS." >&2
    echo "" >&2
fi

# Start the server using uv
echo "Starting MCP Woodpecker CI Server..."
uv run python src/server.py "$@"
