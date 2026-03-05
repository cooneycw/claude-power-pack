#!/bin/bash
# Start the MCP Nano-Banana Diagram Server
# This script uses uv to manage dependencies and run the server

set -euo pipefail

# Change to the server directory
cd "$(dirname "$0")"

# Start the server using uv
echo "Starting MCP Nano-Banana Diagram Server..."
uv run python src/server.py "$@"
