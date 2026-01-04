#!/bin/bash
# Start MCP Playwright Persistent Server
# This script uses uv to manage dependencies and run the server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Start server using uv
echo "Starting Playwright Persistent MCP Server..."
uv run python src/server.py
