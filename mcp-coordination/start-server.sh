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

# Activate conda environment
CONDA_ENV="${CONDA_ENV:-mcp-coordination}"
if command -v conda &>/dev/null; then
    eval "$(conda shell.bash hook)"
    conda activate "$CONDA_ENV"
fi

# Run server
cd src
if [[ "${1:-}" == "--daemon" ]]; then
    exec python server.py
else
    python server.py
fi
