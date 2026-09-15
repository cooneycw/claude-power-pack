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
elif [ -z "${QWEN_OLLAMA_URL:-}" ]; then
    echo "[ ] QWEN_OLLAMA_URL is unset - no serving machine URL was provided, and localhost is not answering."
    echo "    If the model is served on another machine:"
    echo "      export QWEN_OLLAMA_URL=http://<serving-host>:11434"
    echo "    Run /cpp:init and select Tier 6 to persist it (issue #755)."
    echo "    If this is the serving machine, start the service (launchd agent or 'ollama serve')."
else
    echo "[ ] Ollama NOT reachable at $QWEN_ENDPOINT"
    echo "    This endpoint came from QWEN_OLLAMA_URL. Check that the server is"
    echo "    running and that the configured host is correct."
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
if echo "$TAGS" | grep -qF "\"$QWEN_MODEL\""; then
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

### Step 4: Serveability Probe (the check that decides READY)

**This step is not optional, and its result is load-bearing (issue #895).** The
checks above prove the daemon answers and the model is in the catalogue.
Registration and serveability are different facts, and a host can satisfy both
checks while being unable to load the model at all - which is where the qwen
host sat on 2026-09-13.

The probe that separates them is a real single-token generation. It lives in one
audited helper so that this command and the `/qwen:auto` preflight ask the same
question and cannot drift apart. Invoke it BARE at the stable path:

```bash
~/.claude/scripts/lane-serveability-check.sh --endpoint "$QWEN_ENDPOINT" --model "$QWEN_MODEL" --lane qwen
SERVE_EXIT=$?
```

(Exit 127 - not installed: fall back to
`${CLAUDE_PLUGIN_ROOT}/scripts/lane-serveability-check.sh`, else the
CPP-checkout copy, and tell the user to run **`/flow:repair`**. If no copy
exists, leave `SERVE_EXIT` unset: Step 5 then reports the lane as UNVERIFIED
rather than READY, because a probe that did not run is unchecked, not clean.)

Report the verdict, and on `serving` also report throughput from the elapsed
time. `LANE_SERVE_DETAIL` carries the server's own words on a failure - print
them verbatim rather than paraphrasing, because they are what distinguishes a
reaped loader (`signal: killed`, a host memory ceiling) from a model name that
does not exist.

**Why this replaced the previous hand-rolled latency probe.** That probe ran the
right request and then discarded its verdict: it piped the response through
`grep -o '"eval_count"...'` and printed `(probe failed or timed out)` on
failure, but Step 5's `READY` was computed from `command -v qwen` and
`/api/version` alone. So on the broken host this command printed the failure and
then printed `Status: READY` underneath it - and `/qwen:auto` tells a user whose
run just died to come here and look. The diagnostic surface has to be able to
say no, or the handoff lands on a green light.

### Step 5: Summary

```bash
echo ""
echo "==================================="

READY=true
command -v qwen &>/dev/null || READY=false
curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" > /dev/null 2>&1 || READY=false

# The Step 4 serveability verdict decides READY (issue #895). Three states, not
# two: 0 is serving, any other exit is a lane that cannot run, and an UNSET
# SERVE_EXIT means the probe never ran - which is unchecked, not clean, and so
# must not be allowed to report READY either.
#
# `unverified` may only ever WEAKEN a true. A missing harness or an unreachable
# daemon above is a definite NOT READY, and an absent probe cannot soften it
# into a maybe - uncertainty is the weaker claim, so it must never overwrite a
# verdict that was already decided.
if [ "$READY" = "true" ]; then
    if [ -z "${SERVE_EXIT:-}" ]; then
        READY=unverified
    elif [ "$SERVE_EXIT" -ne 0 ]; then
        READY=false
    fi
fi

if [ "$READY" = "true" ]; then
    echo "Status: READY"
    echo ""
    echo "Commands available:"
    echo "  /qwen:auto <ISSUE>   - Full issue lifecycle via local Qwen"
    echo "  /qwen:exec <PROMPT>  - One-shot local Qwen execution"
elif [ "$READY" = "unverified" ]; then
    echo "Status: UNVERIFIED"
    echo ""
    echo "The server answers and the model is registered, but the serveability"
    echo "probe could not be run, so whether this lane can actually serve is"
    echo "UNKNOWN. Install the helper family with /flow:repair and re-run."
else
    echo "Status: NOT READY"
    echo ""
    if [ "${SERVE_EXIT:-0}" -ne 0 ]; then
        echo "The model is registered but could NOT be served - see the Step 4"
        echo "verdict above. Registration and serveability are different facts,"
        echo "and this host satisfies only the first. A 'signal: killed' there"
        echo "means the loader was reaped by the host (a memory ceiling), which"
        echo "is fixed on the serving machine, not in this repo."
    elif [ -z "${QWEN_OLLAMA_URL:-}" ]; then
        echo "Likely cause: QWEN_OLLAMA_URL is unset; /cpp:init Tier 6 can persist it"
    else
        echo "To set up: /cpp:init (select Tier 6 - Local Qwen), or see /qwen:help"
    fi
fi

echo "==================================="
```

## Notes

- This command is read-only - it checks state but does not modify anything
- `QWEN_OLLAMA_URL` lets a remote machine check (and use) the serving machine's stack
- An unset `QWEN_OLLAMA_URL` is diagnosed separately from a configured but
  unreachable endpoint (issue #755)
- The Qwen Code CLI is required only as an agentic harness; `/qwen:*` never uses a cloud API key
