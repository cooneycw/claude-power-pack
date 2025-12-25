#!/bin/bash
# Start MCP Playwright Persistent Server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/src"

# Activate conda environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate mcp-playwright

# Start server
python server.py
