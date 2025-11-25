#!/bin/bash
# Convenient script to start the MCP server in the background

# Get the directory of this script and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables from .env file (in project root)
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading environment from $PROJECT_ROOT/.env"
    set -a  # automatically export all variables
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo "WARNING: .env file not found at $PROJECT_ROOT/.env"
    echo "Create one with: cp .env.example .env (then edit with your API key)"
fi

# Validate API key is set
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your-api-key-here" ]; then
    echo ""
    echo "ERROR: GEMINI_API_KEY is not set!"
    echo ""
    echo "Please edit $PROJECT_ROOT/.env and add your API key:"
    echo "  1. Get your key from: https://aistudio.google.com/apikey"
    echo "  2. Edit: nano $PROJECT_ROOT/.env"
    echo "  3. Replace 'your-api-key-here' with your actual key"
    echo ""
    exit 1
fi

# Set defaults for optional variables
export MCP_SERVER_HOST="${MCP_SERVER_HOST:-127.0.0.1}"
export MCP_SERVER_PORT="${MCP_SERVER_PORT:-8080}"
export ENABLE_CONTEXT_CACHING="${ENABLE_CONTEXT_CACHING:-true}"
export CACHE_TTL_MINUTES="${CACHE_TTL_MINUTES:-60}"

# Start the server using conda (server is now in src/)
echo "Starting MCP Second Opinion Server..."
echo "Host: $MCP_SERVER_HOST"
echo "Port: $MCP_SERVER_PORT"
echo "Context Caching: $ENABLE_CONTEXT_CACHING"

conda run -n mcp-second-opinion --no-capture-output python "$PROJECT_ROOT/src/server.py" &

SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"
echo "To stop: kill $SERVER_PID"
echo "To view logs: tail -f /var/log/syslog | grep mcp-second-opinion"
