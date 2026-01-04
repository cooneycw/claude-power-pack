#!/bin/bash
# start-server.sh - Start MCP Coordination Server
#
# Usage:
#   ./start-server.sh           # Foreground
#   ./start-server.sh --daemon  # Background (for systemd)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables if .env exists
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

# Run server using uv
echo "Starting Coordination MCP Server..."
if [[ "${1:-}" == "--daemon" ]]; then
    exec uv run python src/server.py
else
    uv run python src/server.py
fi
