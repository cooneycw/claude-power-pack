#!/bin/bash
#
# install-service.sh - Generate and install the MCP Playwright Persistent systemd service
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
#   - uv installation path
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

echo -e "${GREEN}MCP Playwright Persistent Service Installer${NC}"
echo "============================================"
echo

# Detect MCP server directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -f "$MCP_SERVER_DIR/src/server.py" ]]; then
    echo -e "${RED}Error: Cannot find server.py in $MCP_SERVER_DIR/src/${NC}"
    exit 1
fi

echo -e "MCP Server Directory: ${GREEN}$MCP_SERVER_DIR${NC}"

# Detect uv
UV_BIN=""
if command -v uv &> /dev/null; then
    UV_BIN="$(dirname "$(which uv)")"
elif [[ -f "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin"
elif [[ -f "$HOME/.cargo/bin/uv" ]]; then
    UV_BIN="$HOME/.cargo/bin"
elif [[ -f "/usr/local/bin/uv" ]]; then
    UV_BIN="/usr/local/bin"
else
    echo -e "${RED}Error: Cannot find uv installation${NC}"
    echo "Install uv with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo -e "uv Binary Directory: ${GREEN}$UV_BIN${NC}"

# Check for pyproject.toml
if [[ ! -f "$MCP_SERVER_DIR/pyproject.toml" ]]; then
    echo -e "${RED}Error: pyproject.toml not found${NC}"
    echo "This server requires a pyproject.toml for uv to manage dependencies"
    exit 1
fi

# Check for Playwright browsers
if ! "$UV_BIN/uv" run --project "$MCP_SERVER_DIR" playwright --version &> /dev/null; then
    echo -e "${YELLOW}Warning: Playwright browsers may not be installed${NC}"
    echo "Install with: uv run --project $MCP_SERVER_DIR playwright install chromium"
fi

# Get current user
SERVICE_USER="$USER"
echo -e "Service User: ${GREEN}$SERVICE_USER${NC}"

# Check for .env file
if [[ ! -f "$MCP_SERVER_DIR/.env" ]]; then
    echo -e "${YELLOW}Note: .env file not found (optional for this server)${NC}"
    echo "Copy from template if needed: cp $MCP_SERVER_DIR/.env.example $MCP_SERVER_DIR/.env"
fi

echo

# Read template and substitute variables
TEMPLATE_FILE="$MCP_SERVER_DIR/deploy/mcp-playwright.service.template"
OUTPUT_FILE="$MCP_SERVER_DIR/deploy/mcp-playwright.service"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo -e "${RED}Error: Template file not found: $TEMPLATE_FILE${NC}"
    exit 1
fi

echo "Generating service file..."

# Substitute variables
sed -e "s|\${SERVICE_USER}|$SERVICE_USER|g" \
    -e "s|\${MCP_SERVER_DIR}|$MCP_SERVER_DIR|g" \
    -e "s|\${UV_BIN}|$UV_BIN|g" \
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
        echo "  systemctl --user enable mcp-playwright"
        echo "  systemctl --user start mcp-playwright"
    else
        echo "  sudo cp $OUTPUT_FILE /etc/systemd/system/"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable mcp-playwright"
        echo "  sudo systemctl start mcp-playwright"
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
    echo "  systemctl --user enable mcp-playwright  # Enable on login"
    echo "  systemctl --user start mcp-playwright   # Start now"
    echo "  systemctl --user status mcp-playwright  # Check status"
    echo "  journalctl --user -u mcp-playwright -f  # View logs"
else
    echo "Installing as system service (requires sudo)..."
    sudo cp "$OUTPUT_FILE" /etc/systemd/system/
    sudo systemctl daemon-reload

    echo -e "${GREEN}Service installed successfully!${NC}"
    echo
    echo "Commands:"
    echo "  sudo systemctl enable mcp-playwright  # Enable on boot"
    echo "  sudo systemctl start mcp-playwright   # Start now"
    echo "  sudo systemctl status mcp-playwright  # Check status"
    echo "  sudo journalctl -u mcp-playwright -f  # View logs"
fi

echo
echo -e "${GREEN}Done!${NC}"
