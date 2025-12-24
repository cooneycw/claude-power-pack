#!/bin/bash
#
# install-service.sh - Generate and install the MCP Second Opinion systemd service
#
# Usage:
#   ./install-service.sh [OPTIONS]
#
# Options:
#   --user          Install as user service (default, no sudo required)
#   --system        Install as system service (requires sudo)
#   --generate-only Just generate the service file, don't install
#   --help          Show this help message
#
# The script auto-detects:
#   - MCP server directory (from git repository root)
#   - Conda installation path
#   - Current user

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default options
INSTALL_MODE="user"
GENERATE_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --user)
            INSTALL_MODE="user"
            shift
            ;;
        --system)
            INSTALL_MODE="system"
            shift
            ;;
        --generate-only)
            GENERATE_ONLY=true
            shift
            ;;
        --help|-h)
            head -20 "$0" | tail -18
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}MCP Second Opinion Service Installer${NC}"
echo "======================================"
echo

# Detect MCP server directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -f "$MCP_SERVER_DIR/src/server.py" ]]; then
    echo -e "${RED}Error: Cannot find server.py in $MCP_SERVER_DIR/src/${NC}"
    exit 1
fi

echo -e "MCP Server Directory: ${GREEN}$MCP_SERVER_DIR${NC}"

# Detect conda
CONDA_BIN=""
if command -v conda &> /dev/null; then
    CONDA_BIN="$(dirname "$(which conda)")"
elif [[ -d "$HOME/miniconda3/bin" ]]; then
    CONDA_BIN="$HOME/miniconda3/bin"
elif [[ -d "$HOME/anaconda3/bin" ]]; then
    CONDA_BIN="$HOME/anaconda3/bin"
elif [[ -d "/opt/conda/bin" ]]; then
    CONDA_BIN="/opt/conda/bin"
else
    echo -e "${RED}Error: Cannot find conda installation${NC}"
    echo "Please ensure conda is installed and in your PATH"
    exit 1
fi

echo -e "Conda Binary Directory: ${GREEN}$CONDA_BIN${NC}"

# Verify conda environment exists
if ! "$CONDA_BIN/conda" env list | grep -q "mcp-second-opinion"; then
    echo -e "${YELLOW}Warning: conda environment 'mcp-second-opinion' not found${NC}"
    echo "Create it with: conda env create -f $MCP_SERVER_DIR/environment.yml"
fi

# Get current user
SERVICE_USER="$USER"
echo -e "Service User: ${GREEN}$SERVICE_USER${NC}"

# Check for .env file
if [[ ! -f "$MCP_SERVER_DIR/.env" ]]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Copy from template: cp $MCP_SERVER_DIR/.env.example $MCP_SERVER_DIR/.env"
    echo "Then add your API keys"
fi

echo

# Read template and substitute variables
TEMPLATE_FILE="$MCP_SERVER_DIR/deploy/mcp-second-opinion.service.template"
OUTPUT_FILE="$MCP_SERVER_DIR/deploy/mcp-second-opinion.service"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo -e "${RED}Error: Template file not found: $TEMPLATE_FILE${NC}"
    exit 1
fi

echo "Generating service file..."

# Substitute variables
sed -e "s|\${SERVICE_USER}|$SERVICE_USER|g" \
    -e "s|\${MCP_SERVER_DIR}|$MCP_SERVER_DIR|g" \
    -e "s|\${CONDA_BIN}|$CONDA_BIN|g" \
    "$TEMPLATE_FILE" > "$OUTPUT_FILE"

# For user services, remove User= directive (not allowed) and fix WantedBy target
if [[ "$INSTALL_MODE" == "user" ]]; then
    sed -i -e '/^User=/d' \
           -e 's/WantedBy=multi-user.target/WantedBy=default.target/' \
           "$OUTPUT_FILE"
fi

echo -e "Generated: ${GREEN}$OUTPUT_FILE${NC}"

if $GENERATE_ONLY; then
    echo
    echo "Service file generated. To install manually:"
    if [[ "$INSTALL_MODE" == "user" ]]; then
        echo "  mkdir -p ~/.config/systemd/user"
        echo "  cp $OUTPUT_FILE ~/.config/systemd/user/"
        echo "  systemctl --user daemon-reload"
        echo "  systemctl --user enable mcp-second-opinion"
        echo "  systemctl --user start mcp-second-opinion"
    else
        echo "  sudo cp $OUTPUT_FILE /etc/systemd/system/"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable mcp-second-opinion"
        echo "  sudo systemctl start mcp-second-opinion"
    fi
    exit 0
fi

# Install the service
echo
if [[ "$INSTALL_MODE" == "user" ]]; then
    echo "Installing as user service..."
    mkdir -p ~/.config/systemd/user
    cp "$OUTPUT_FILE" ~/.config/systemd/user/
    systemctl --user daemon-reload

    echo -e "${GREEN}Service installed successfully!${NC}"
    echo
    echo "Commands:"
    echo "  systemctl --user enable mcp-second-opinion  # Enable on login"
    echo "  systemctl --user start mcp-second-opinion   # Start now"
    echo "  systemctl --user status mcp-second-opinion  # Check status"
    echo "  journalctl --user -u mcp-second-opinion -f  # View logs"
else
    echo "Installing as system service (requires sudo)..."
    sudo cp "$OUTPUT_FILE" /etc/systemd/system/
    sudo systemctl daemon-reload

    echo -e "${GREEN}Service installed successfully!${NC}"
    echo
    echo "Commands:"
    echo "  sudo systemctl enable mcp-second-opinion  # Enable on boot"
    echo "  sudo systemctl start mcp-second-opinion   # Start now"
    echo "  sudo systemctl status mcp-second-opinion  # Check status"
    echo "  sudo journalctl -u mcp-second-opinion -f  # View logs"
fi

echo
echo -e "${GREEN}Done!${NC}"
