#!/bin/bash
# Start the Second Opinion MCP Server
# This script uses uv to manage dependencies and run the server

set -euo pipefail

# Change to the server directory
cd "$(dirname "$0")"

# Pre-flight: check uv is available
if ! command -v uv &>/dev/null; then
    echo "ERROR: 'uv' not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# Pre-flight: check .env or environment variables
if [[ ! -f .env ]] && [[ -z "${GEMINI_API_KEY:-}" ]] && [[ -z "${OPENAI_API_KEY:-}" ]] && [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "WARNING: No .env file and no API keys in environment." >&2
    echo "  The server will start but all tool calls will fail." >&2
    echo "  Copy .env.example to .env and add at least one API key:" >&2
    echo "    cp .env.example .env" >&2
    echo "    # Edit .env with your API keys" >&2
    echo "" >&2
fi

# Handle --diagnose flag
if [[ "${1:-}" == "--diagnose" ]]; then
    echo "Running diagnostics..."
    uv run python src/server.py --diagnose
    exit $?
fi

# Start the server using uv
echo "Starting Second Opinion MCP Server..."
uv run python src/server.py "$@"
