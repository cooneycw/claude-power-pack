---
description: Check local Qwen serving stack - Ollama server, model, and Codex harness readiness
allowed-tools: Bash(codex:*), Bash(ollama:*), Bash(command -v:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(curl:*), Bash(test:*), Bash(head:*), Bash(launchctl:*)
---

# Qwen Status: Check Local Qwen Stack Readiness

Check the Ollama server, the Qwen model, network exposure, and the Codex CLI
harness that `/qwen:auto` and `/qwen:exec` depend on.

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

### Step 3: Check Codex CLI Harness

```bash
echo ""
echo "=== Codex CLI Harness ==="
echo ""

if command -v codex &>/dev/null; then
    CODEX_VERSION=$(codex --version 2>/dev/null || echo "unknown")
    echo "[x] Codex CLI: $CODEX_VERSION"
    if codex exec --help 2>&1 | grep -q -- "--oss"; then
        echo "[x] --oss local-provider support: present"
    else
        echo "[ ] --oss flag not supported - upgrade: npm install -g @openai/codex"
    fi
else
    echo "[ ] Codex CLI: not installed (required as the local-model harness)"
    echo "    Install with: npm install -g @openai/codex"
    echo "    NOTE: no OpenAI API key is needed for /qwen:* usage"
fi

# Remote profile, if configured
if [ -n "$QWEN_CODEX_PROFILE" ]; then
    echo ""
    if grep -q "\[profiles.$QWEN_CODEX_PROFILE\]" ~/.codex/config.toml 2>/dev/null; then
        echo "[x] Remote profile '$QWEN_CODEX_PROFILE' found in ~/.codex/config.toml"
    else
        echo "[ ] QWEN_CODEX_PROFILE='$QWEN_CODEX_PROFILE' set but not found in ~/.codex/config.toml"
        echo "    See /qwen:help for the profile recipe"
    fi
fi
```

### Step 4: Latency Probe (optional, serving machine only)

If the server and model are present, offer a quick generation probe:

```bash
echo ""
echo "=== Latency Probe ==="
curl -s "$QWEN_ENDPOINT/api/generate" \
  -d "{\"model\":\"$QWEN_MODEL\",\"prompt\":\"Say OK. /no_think\",\"stream\":false}" \
  --max-time 120 | grep -o '"eval_count":[0-9]*\|"eval_duration":[0-9]*' || echo "(probe failed or timed out)"
```

Report tokens/second if the probe succeeds (eval_count / (eval_duration / 1e9)).

### Step 5: Summary

```bash
echo ""
echo "==================================="

READY=true
command -v codex &>/dev/null || READY=false
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
- `QWEN_OLLAMA_URL` lets a remote machine check the serving machine's stack
- The Codex CLI is required only as an agentic harness; `/qwen:*` never uses an OpenAI API key
