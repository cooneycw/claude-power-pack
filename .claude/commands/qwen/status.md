---
description: Check local Qwen serving stack - Ollama server, model, and Qwen Code harness readiness
allowed-tools: Bash(qwen:*), Bash(ollama:*), Bash(command -v:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(curl:*), Bash(test:*), Bash(head:*), Bash(launchctl:*)
---

# Qwen Status: Check Local Qwen Stack Readiness

Check the Ollama server, the Qwen model, network exposure, and the Qwen Code
CLI harness that `/qwen:auto` and `/qwen:exec` depend on.

## Instructions

When the user invokes `/qwen:status`, run these checks and report:

### Step 1: Check Ollama Server

```bash
echo "=== Ollama Server ==="
echo ""

QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"

VERSION_JSON=$(curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" 2>/dev/null)
if [ -n "$VERSION_JSON" ]; then
    echo "[x] Ollama reachable at $QWEN_ENDPOINT: $VERSION_JSON"
else
    echo "[ ] Ollama NOT reachable at $QWEN_ENDPOINT"
    echo "    Local machine: start the service (launchd agent or 'ollama serve')"
    echo "    Remote machine: set QWEN_OLLAMA_URL to the serving machine's URL"
fi

# On the serving machine, report network exposure
if command -v ollama &>/dev/null && [ "$QWEN_ENDPOINT" = "http://127.0.0.1:11434" ]; then
    if grep -q "OLLAMA_HOST" ~/Library/LaunchAgents/com.*.ollama.plist 2>/dev/null; then
        echo "[x] Network binding: OLLAMA_HOST configured in launchd agent (LAN/tailnet reachable)"
    else
        echo "[~] Network binding: localhost only (other machines cannot reach this server)"
    fi
fi
```

### Step 2: Check Model

```bash
echo ""
echo "=== Qwen Model ==="
echo ""

QWEN_MODEL="${QWEN_MODEL:-qwen3.8-code:latest}"

TAGS=$(curl -sf --max-time 5 "$QWEN_ENDPOINT/api/tags" 2>/dev/null)
if echo "$TAGS" | grep -q "${QWEN_MODEL%%:*}"; then
    echo "[x] Model available: $QWEN_MODEL"
else
    echo "[ ] Model '$QWEN_MODEL' not found on the server"
    echo "    On the serving machine: ollama pull qwen3.8:27b"
    echo "    then create the tuned tag per /qwen:help"
fi

# Show what is currently loaded (serving machine only)
if command -v ollama &>/dev/null; then
    echo ""
    echo "Loaded models:"
    ollama ps 2>/dev/null || echo "  (unable to query)"
fi
```

### Step 3: Check Qwen Code CLI Harness

```bash
echo ""
echo "=== Qwen Code CLI Harness ==="
echo ""

if command -v qwen &>/dev/null; then
    QWEN_CLI_VERSION=$(qwen --version 2>/dev/null || echo "unknown")
    echo "[x] Qwen Code CLI: $QWEN_CLI_VERSION"
    if qwen --help 2>&1 | grep -q -- "--output-format"; then
        echo "[x] Headless stream-json support: present"
    else
        echo "[ ] --output-format not supported - upgrade: npm install -g @qwen-code/qwen-code"
    fi
else
    echo "[ ] Qwen Code CLI: not installed (required as the local-model harness)"
    echo "    Install with: npm install -g @qwen-code/qwen-code"
    echo "    NOTE: no cloud API key is needed for /qwen:* usage"
fi

# Flag the retired Codex harness path if its env var is still set
if [ -n "$QWEN_CODEX_PROFILE" ]; then
    echo ""
    echo "[~] QWEN_CODEX_PROFILE is set but no longer used: the Codex CLI"
    echo "    harness was retired (issue #745). Remote serving machines now"
    echo "    need only QWEN_OLLAMA_URL - see /qwen:help. Unset it."
fi
```

### Step 4: Latency Probe (optional, serving machine only)

If the server and model are present, offer a quick generation probe:

```bash
echo ""
echo "=== Latency Probe ==="
curl -s "$QWEN_ENDPOINT/api/generate" \
  -d "{\"model\":\"$QWEN_MODEL\",\"prompt\":\"Say OK.\",\"think\":false,\"stream\":false}" \
  --max-time 120 | grep -o '"eval_count":[0-9]*\|"eval_duration":[0-9]*' || echo "(probe failed or timed out)"
```

Report tokens/second if the probe succeeds (eval_count / (eval_duration / 1e9)).
(`"think": false` keeps the probe fast on thinking-enabled models; it is the
native-API hard switch, more reliable than the `/no_think` soft prompt.)

### Step 5: Summary

```bash
echo ""
echo "==================================="

READY=true
command -v qwen &>/dev/null || READY=false
curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" > /dev/null 2>&1 || READY=false

if [ "$READY" = "true" ]; then
    echo "Status: READY"
    echo ""
    echo "Commands available:"
    echo "  /qwen:auto <ISSUE>   - Full issue lifecycle via local Qwen"
    echo "  /qwen:exec <PROMPT>  - One-shot local Qwen execution"
else
    echo "Status: NOT READY"
    echo ""
    echo "To set up: /cpp:init (select Tier 6 - Local Qwen), or see /qwen:help"
fi

echo "==================================="
```

## Notes

- This command is read-only - it checks state but does not modify anything
- `QWEN_OLLAMA_URL` lets a remote machine check (and use) the serving machine's stack
- The Qwen Code CLI is required only as an agentic harness; `/qwen:*` never uses a cloud API key
