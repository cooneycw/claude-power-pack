#!/bin/bash
# Interactive script to set up your Gemini API key

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

echo "========================================"
echo "  MCP Second Opinion - API Key Setup"
echo "========================================"
echo ""

# Check if .env exists
if [ -f "$ENV_FILE" ]; then
    echo "✓ Found existing .env file at: $ENV_FILE"

    # Check if API key is set
    source "$ENV_FILE"
    if [ -n "$GEMINI_API_KEY" ] && [ "$GEMINI_API_KEY" != "your-api-key-here" ]; then
        echo "✓ API key is already configured (starts with: ${GEMINI_API_KEY:0:10}...)"
        echo ""
        read -p "Do you want to update it? (y/N): " update
        if [ "$update" != "y" ] && [ "$update" != "Y" ]; then
            echo "Keeping existing API key."
            exit 0
        fi
    else
        echo "⚠ API key not set or using placeholder value"
    fi
else
    echo "Creating new .env file from template..."
    cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "✓ Created $ENV_FILE"
fi

echo ""
echo "To get your Gemini API key:"
echo "  1. Visit: https://aistudio.google.com/apikey"
echo "  2. Sign in with your Google account"
echo "  3. Click 'Create API Key' or copy existing key"
echo ""
read -p "Enter your Gemini API key: " api_key

if [ -z "$api_key" ]; then
    echo "ERROR: No API key entered. Exiting."
    exit 1
fi

# Validate format (basic check)
if [ ${#api_key} -lt 20 ]; then
    echo "WARNING: API key seems too short (${#api_key} characters)"
    read -p "Are you sure this is correct? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Cancelled."
        exit 1
    fi
fi

# Update .env file
sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$api_key|" "$ENV_FILE"

echo ""
echo "✅ API key saved to $ENV_FILE"
echo "✅ File permissions set to 600 (owner read/write only)"
echo ""
echo "Next steps:"
echo "  1. Test the configuration:"
echo "     ./start-server.sh"
echo ""
echo "  2. Update Claude Code config (~/.config/claude-code/config.json):"
echo "     See DEPLOYMENT_QUICKSTART.md for details"
echo ""
