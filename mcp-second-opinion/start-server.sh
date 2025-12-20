#!/bin/bash
# Start the Second Opinion MCP Server
# This script activates the conda environment and starts the server

# Source conda
source ~/miniconda3/etc/profile.d/conda.sh

# Activate the environment
conda activate mcp-second-opinion

# Change to the server directory
cd "$(dirname "$0")"

# Start the server
echo "Starting Second Opinion MCP Server..."
python src/server.py
