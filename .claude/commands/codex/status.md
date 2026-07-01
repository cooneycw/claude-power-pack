---
description: Check Codex CLI installation, config, and readiness
allowed-tools: Bash(codex:*), Bash(command -v:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(npm:*), Bash(node:*), Bash(test:*), Bash(head:*)
---

# Codex Status: Check Codex CLI Readiness

Check Codex CLI installation, configuration, and MCP server registrations.

## Instructions

When the user invokes `/codex:status`, run these checks and report:

### Step 1: Check Codex CLI

```bash
echo "=== Codex CLI ==="
echo ""

# Check if installed
if command -v codex &>/dev/null; then
    CODEX_VERSION=$(codex --version 2>/dev/null || echo "unknown")
    CODEX_PATH=$(command -v codex)
    echo "[x] Codex CLI: $CODEX_VERSION"
    echo "    Path: $CODEX_PATH"
else
    echo "[ ] Codex CLI: not installed"
    echo "    Install with: npm install -g @openai/codex"
    echo ""
    echo "Status: NOT READY"
    exit 0
fi
```

### Step 2: Check Codex Doctor

```bash
echo ""
echo "=== Codex Doctor ==="
echo ""

DOCTOR_OUTPUT=$(codex doctor 2>&1 || true)
echo "$DOCTOR_OUTPUT"

if echo "$DOCTOR_OUTPUT" | grep -qi "error\|fail\|missing"; then
    echo ""
    echo "[!] codex doctor reported issues - resolve before using /codex:auto"
else
    echo ""
    echo "[x] codex doctor: all checks passed"
fi
```

### Step 3: Check Codex Configuration

```bash
echo ""
echo "=== Codex Configuration ==="
echo ""

# Check config file
CODEX_CONFIG="$HOME/.codex/config.toml"
if [ -f "$CODEX_CONFIG" ]; then
    echo "[x] Config: $CODEX_CONFIG"
    # Show model config (without exposing keys)
    grep -E '^(model|provider)' "$CODEX_CONFIG" 2>/dev/null | head -5 || echo "    (no model/provider settings found)"
else
    echo "[ ] Config: $CODEX_CONFIG not found"
    echo "    Run: codex login"
fi

# Check for OpenAI API key
if [ -n "$OPENAI_API_KEY" ]; then
    echo "[x] OPENAI_API_KEY: set in environment"
else
    echo "[ ] OPENAI_API_KEY: not set in environment"
    echo "    Set via: export OPENAI_API_KEY=... or codex login"
fi
```

### Step 4: Check MCP Registrations

```bash
echo ""
echo "=== MCP Registrations (Codex) ==="
echo ""

if command -v codex &>/dev/null; then
    CODEX_MCP=$(codex mcp list 2>/dev/null || echo "")
    if [ -n "$CODEX_MCP" ]; then
        for server in second-opinion playwright-persistent nano-banana; do
            if echo "$CODEX_MCP" | grep -q "$server"; then
                echo "[x] $server: registered with Codex"
            else
                echo "[ ] $server: not registered with Codex"
            fi
        done
    else
        echo "[ ] No MCP servers registered with Codex"
        echo "    Register via /cpp:init (Tier 5) or manually:"
        echo "    codex mcp add <name> --url http://127.0.0.1:<port>/mcp"
    fi
fi
```

### Step 5: Summary

```bash
echo ""
echo "==================================="

# Determine readiness
READY=true
if ! command -v codex &>/dev/null; then READY=false; fi
if [ -z "$OPENAI_API_KEY" ] && ! [ -f "$HOME/.codex/config.toml" ]; then READY=false; fi

if [ "$READY" = "true" ]; then
    echo "Status: READY"
    echo ""
    echo "Commands available:"
    echo "  /codex:auto <ISSUE>  - Full issue lifecycle via Codex"
    echo "  /codex:exec <PROMPT> - One-shot Codex execution"
    echo "  /codex:ask <QUESTION> - Read-only question, relayed answer"
else
    echo "Status: NOT READY"
    echo ""
    echo "To set up:"
    echo "  1. npm install -g @openai/codex"
    echo "  2. codex login (or set OPENAI_API_KEY)"
    echo "  3. codex doctor"
    echo "  4. /cpp:init (select Tier 5 for MCP registration)"
fi

echo "==================================="
```

## Notes

- This command is read-only - it checks state but does not modify anything
- Run `/cpp:init` and select Tier 5 to install and configure Codex
- Codex CLI requires Node.js and an OpenAI API key
