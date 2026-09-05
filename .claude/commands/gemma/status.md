---
description: Check local Gemma serving stack - Ollama server, model, and OpenCode harness readiness
allowed-tools: Bash(opencode:*), Bash(ollama:*), Bash(command -v:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(curl:*), Bash(test:*), Bash(head:*), Bash(tail:*)
---

# Gemma Status: Check Local Gemma Stack Readiness

Check the Ollama server, the `gemma4-code` model, the OpenCode provider
config, and a real tool-calling smoke test that `/gemma:auto` and
`/gemma:exec` depend on.

## Instructions

When the user invokes `/gemma:status`, run these checks and report:

### Step 1: Check Ollama Server

```bash
echo "=== Ollama Server ==="
echo ""

GEMMA_ENDPOINT="${GEMMA_OLLAMA_URL:-http://127.0.0.1:11434}"

VERSION_JSON=$(curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/version" 2>/dev/null)
if [ -n "$VERSION_JSON" ]; then
    echo "[x] Ollama reachable at $GEMMA_ENDPOINT: $VERSION_JSON"
elif [ -z "${GEMMA_OLLAMA_URL:-}" ]; then
    echo "[ ] GEMMA_OLLAMA_URL is unset - no serving machine URL was provided, and localhost is not answering."
    echo "    If the model is served on another machine:"
    echo "      export GEMMA_OLLAMA_URL=http://<serving-host>:11434"
    echo "    Run /cpp:init and select Tier 7 to persist it (issue #755)."
    echo "    If this is the serving machine, start the service ('ollama serve')."
else
    echo "[ ] Ollama NOT reachable at $GEMMA_ENDPOINT"
    echo "    This endpoint came from GEMMA_OLLAMA_URL. Check that the server is"
    echo "    running and that the configured host is correct."
fi
```

### Step 2: Check Model

```bash
echo ""
echo "=== Gemma Model ==="
echo ""

GEMMA_MODEL="${GEMMA_MODEL:-gemma4-code:latest}"

TAGS=$(curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/tags" 2>/dev/null)
if echo "$TAGS" | grep -q "${GEMMA_MODEL%%:*}"; then
    echo "[x] Model available: $GEMMA_MODEL"
else
    echo "[ ] Model '$GEMMA_MODEL' not found on the server"
    echo "    On the serving machine, create the tuned tag (see /gemma:help):"
    echo "      printf 'FROM gemma4:31b-it-qat\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.2\n' > /tmp/Modelfile.gemma4-code"
    echo "      ollama create gemma4-code -f /tmp/Modelfile.gemma4-code"
fi

# Show what is currently loaded and confirm GPU residency (serving machine only)
if command -v ollama &>/dev/null; then
    echo ""
    echo "Loaded models:"
    OLLAMA_PS=$(ollama ps 2>/dev/null)
    echo "$OLLAMA_PS"
    if echo "$OLLAMA_PS" | grep "${GEMMA_MODEL%%:*}" | grep -qv "100% GPU"; then
        echo ""
        echo "[!] WARNING: model is not 100% GPU resident - a layer has spilled to"
        echo "    CPU. Throughput will collapse from ~30 tok/s to unusable. Check"
        echo "    VRAM headroom (nvidia-smi) or lower num_ctx (see /gemma:help)."
    fi
fi
```

### Step 3: Check OpenCode Harness and Provider Resolution

```bash
echo ""
echo "=== OpenCode Harness ==="
echo ""

if command -v opencode &>/dev/null; then
    OPENCODE_VERSION=$(opencode --version 2>/dev/null || echo "unknown")
    echo "[x] OpenCode CLI: $OPENCODE_VERSION"
else
    echo "[ ] OpenCode CLI: not installed (required as the local-model harness)"
    echo "    Install with: npm install -g opencode-ai"
    echo "    NOTE: no cloud API key is needed for /gemma:* usage"
fi

# The gemma-ollama provider must resolve to confirm:
#   (a) the ai-sdk-ollama npm package installed cleanly (it is resolved by
#       OpenCode on first use, not vendored - this step CAN fail on a fresh
#       machine, offline, or behind a proxy, and it fails as a provider
#       error, not a "missing package" error)
#   (b) the provider/model pairing in opencode.json is actually wired up
if command -v opencode &>/dev/null; then
    PROVIDER_LIST=$(timeout 30 opencode models 2>&1)
    if echo "$PROVIDER_LIST" | grep -q "^gemma-ollama/"; then
        echo "[x] Provider resolves: $(echo "$PROVIDER_LIST" | grep '^gemma-ollama/')"
    else
        echo "[ ] Provider 'gemma-ollama' did NOT resolve via 'opencode models'"
        echo "    Check ~/.config/opencode/opencode.json has a 'gemma-ollama'"
        echo "    provider block (npm: ai-sdk-ollama) - see /gemma:help. If the"
        echo "    config is present, this is likely the dynamic npm dependency"
        echo "    failing to install (offline, proxy, or npm registry issue)."
    fi
fi

# The gemma-implementer agent carries the MECHANICAL fence: a permission block
# that denies git commit/push, gh, deploy, and out-of-directory writes outright
# (issue #752). OpenCode has no --sandbox flag, so this profile - not a
# container - is what stops a wandering local model from running the lifecycle
# itself. Without it, /gemma:auto would be running on the textual fence alone.
if command -v opencode &>/dev/null; then
    if echo "$PROVIDER_LIST" | grep -q "gemma-implementer" \
       || grep -q '"gemma-implementer"' ~/.config/opencode/opencode.json 2>/dev/null; then
        echo "[x] Agent profile 'gemma-implementer' configured (mechanical fence)"
    else
        echo "[ ] Agent 'gemma-implementer' NOT found in ~/.config/opencode/opencode.json"
        echo "    /gemma:auto and /gemma:exec would fall back to the textual fence"
        echo "    alone. Install it from templates/opencode-gemma.json (see"
        echo "    /gemma:help) or re-run /cpp:init and select Tier 7."
    fi
fi
```

### Step 4: Tool-Calling Pre-Flight Smoke Test (native API guard)

**This is the load-bearing check, not a formality.** OpenCode's documented
default for Ollama is the OpenAI-compatible `/v1` provider
(`@ai-sdk/openai-compatible`), which silently drops tool calls once the
system prompt exceeds ~1,600 tokens (ollama/ollama#14958) - and OpenCode's
own agentic system prompt is always well past that (~6,900 tokens measured).
A `/v1` regression - a config edit, an OpenCode upgrade that changes the
provider default, a fresh install following OpenCode's own docs instead of
`/gemma:help` - would otherwise go undetected: `gemma:status` would report
green, and `gemma:auto` would silently produce prose instead of edits on
every run.

A short prompt against a bare `/api/chat` call is NOT a valid guard here -
it passes on both `/v1` and native `/api/chat`, so it would prove nothing.
The guard only works because it runs a REAL `opencode run` invocation and
therefore inherits OpenCode's full ~6,900-token system prompt - past the
threshold where `/v1` fails and native `/api/chat` does not. Do not
"simplify" this to a raw curl smoke test.

```bash
echo ""
echo "=== Tool-Calling Pre-Flight (native /api/chat guard) ==="
echo ""

if command -v opencode &>/dev/null && echo "$PROVIDER_LIST" | grep -q "^gemma-ollama/"; then
    SMOKE_DIR=$(mktemp -d)
    echo "smoke-test-marker" > "$SMOKE_DIR/probe.txt"

    SMOKE_OUTPUT=$(cd "$SMOKE_DIR" && timeout 90 opencode run \
        "List the files in the current directory using your tools." \
        -m "gemma-ollama/${GEMMA_MODEL%%:*}" --agent gemma-implementer \
        --format json --auto 2>&1)
    SMOKE_EXIT=$?

    rm -rf "$SMOKE_DIR"

    if [ "$SMOKE_EXIT" -eq 0 ] && echo "$SMOKE_OUTPUT" | grep -q '"type":"tool_use"' && echo "$SMOKE_OUTPUT" | grep -q '"status":"completed"'; then
        INPUT_TOKENS=$(echo "$SMOKE_OUTPUT" | grep -o '"input":[0-9]*' | head -1 | grep -o '[0-9]*')
        echo "[x] Forced tool call succeeded through the full harness (input ~${INPUT_TOKENS:-unknown} tokens - past the /v1 drop threshold)"
    else
        echo "[ ] FAILED: no tool call observed, or the run errored (exit $SMOKE_EXIT)"
        echo "    This is the exact failure signature of the /v1 tool-call-drop bug:"
        echo "    a plausible text answer with no tool_use event. Verify"
        echo "    ~/.config/opencode/opencode.json still uses 'ai-sdk-ollama' for"
        echo "    the gemma-ollama provider, not '@ai-sdk/openai-compatible'."
        echo "    Last output:"
        echo "$SMOKE_OUTPUT" | tail -15
    fi
else
    echo "[ ] Skipped: harness or provider not ready (see above)"
fi
```

### Step 5: Summary

```bash
echo ""
echo "==================================="

READY=true
command -v opencode &>/dev/null || READY=false
curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/version" > /dev/null 2>&1 || READY=false
echo "$PROVIDER_LIST" | grep -q "^gemma-ollama/" || READY=false
grep -q '"gemma-implementer"' ~/.config/opencode/opencode.json 2>/dev/null || READY=false
[ "$SMOKE_EXIT" = "0" ] || READY=false

if [ "$READY" = "true" ]; then
    echo "Status: READY"
    echo ""
    echo "Commands available:"
    echo "  /gemma:auto <ISSUE>   - Full issue lifecycle via local Gemma"
    echo "  /gemma:exec <PROMPT>  - One-shot local Gemma execution"
else
    echo "Status: NOT READY"
    echo ""
    if [ -z "${GEMMA_OLLAMA_URL:-}" ]; then
        echo "Likely cause: GEMMA_OLLAMA_URL is unset; /cpp:init Tier 7 can persist it"
    else
        echo "See /gemma:help for setup (endpoint, Modelfile, OpenCode provider config)"
    fi
fi

echo "==================================="
```

## Notes

- This command is read-only except for a throwaway probe directory created
  and removed by the Step 4 smoke test - it does not modify the repo
- `GEMMA_OLLAMA_URL` lets a consumer machine check (and use) the serving
  machine's stack; it must be set BEFORE invoking `opencode`, since the
  provider's `baseURL` in `~/.config/opencode/opencode.json` is
  `{env:GEMMA_OLLAMA_URL}` (OpenCode's env-var substitution, resolved at
  invocation time, not hardcoded)
- An unset `GEMMA_OLLAMA_URL` is diagnosed separately from a configured but
  unreachable endpoint (issue #755)
- The OpenCode CLI is required only as an agentic harness; `/gemma:*` never
  uses a cloud API key
- Step 4 is the one check that actually exercises the failure mode from
  ollama/ollama#14958 - keep it running through `opencode run`, never
  through a bare API call
- The `gemma-implementer` agent profile is the mechanical fence (OpenCode has
  no `--sandbox` flag): its `permission.bash` deny rules and
  `external_directory: deny` are what block git/gh/deploy overreach. Step 3
  checks it because a missing profile downgrades `/gemma:auto` to the textual
  fence alone, silently
- NOT READY can be a scheduling fact rather than a broken install: on the
  reference server (proxVMgemma23) the GPU claim is shared with VMs 102/139
  and only one may hold it at a time, so an unreachable endpoint may simply
  mean another VM has the card. Every probe here carries `--max-time` so the
  command fails fast instead of hanging
