#!/bin/bash
# Start the Second Opinion MCP Server
# This script uses uv to manage dependencies and run the server

set -euo pipefail

# Change to the server directory
cd "$(dirname "$0")"

# Start the server using uv
echo "Starting Second Opinion MCP Server..."
uv run python src/server.py
