---
description: One-shot local Qwen execution in current directory with JSONL monitoring
allowed-tools: Bash(qwen:*), Bash(ollama:*), Bash(git:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(curl:*), Bash(head:*), Bash(tail:*), Bash(wc:*), Bash(test:*), Bash(pwd), Bash(tee:*)
---

# Qwen Exec: One-Shot Local Qwen Execution

Run the local Qwen model (via the Qwen Code CLI harness) in the current
directory with JSONL monitoring. For quick tasks without the full issue
lifecycle. Zero API cost - the model runs on local hardware through Ollama.

## Arguments

- `PROMPT` (required): The task prompt (e.g., `"Add input validation to the login form"`)

## Environment

- `QWEN_MODEL` (optional): Ollama model tag. Default: `qwen3.8-code:latest`.
- `QWEN_OLLAMA_URL` (optional): base URL of the Ollama server for remote
  serving machines (e.g., `http://<tailscale-ip>:11434`). Default:
  `http://127.0.0.1:11434`. See `/qwen:help`.

## Instructions

When the user invokes `/qwen:exec <PROMPT>`, perform these steps:

### Step 1: Verify Availability

```bash
if ! command -v qwen &>/dev/null; then
    echo "ERROR: Qwen Code CLI not found (required as the local-model harness)."
    echo "Install with: npm install -g @qwen-code/qwen-code"
    exit 1
fi

QWEN_MODEL="${QWEN_MODEL:-qwen3.8-code:latest}"
QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"

if ! curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" > /dev/null; then
    echo "ERROR: Ollama not reachable at $QWEN_ENDPOINT. Run /qwen:status to diagnose."
    echo "Remote serving machine: set QWEN_OLLAMA_URL=http://<serving-ip>:11434"
    exit 1
fi

echo "Harness: qwen $(qwen --version 2>/dev/null)"
echo "Model:   $QWEN_MODEL via $QWEN_ENDPOINT"
echo "Working directory: $(pwd)"

# Sandbox detection (issue #749): Docker sandbox containers cannot reach
# Tailscale or other host-only network interfaces. When the Ollama endpoint
# is remote, skip --sandbox and rely on the execution fence + overrun
# verification (the two layers that are always active regardless).
# QWEN_FORCE_SANDBOX overrides the automatic detection (1 = force on, 0 = force off).
if [ "${QWEN_FORCE_SANDBOX:-}" = "1" ]; then
    SANDBOX_FLAG="--sandbox"
    echo "Sandbox forced on (QWEN_FORCE_SANDBOX=1)."
elif [ "${QWEN_FORCE_SANDBOX:-}" = "0" ]; then
    SANDBOX_FLAG=""
    echo "Sandbox forced off (QWEN_FORCE_SANDBOX=0)."
else
    SANDBOX_FLAG="--sandbox"
    ENDPOINT_HOST=$(echo "$QWEN_ENDPOINT" | sed -E 's|^https?://||' | sed -E 's|:[0-9]+.*||' | sed -E 's|/.*||')
    case "$ENDPOINT_HOST" in
        127.0.0.1|localhost|::1|"[::1]")
            echo "Ollama endpoint is local ($ENDPOINT_HOST) - sandbox enabled."
            ;;
        *)
            SANDBOX_FLAG=""
            echo "Ollama endpoint is remote ($ENDPOINT_HOST) - sandbox skipped (issue #749)."
            echo "Safety layers active: execution fence + post-execution overrun verification."
            ;;
    esac
fi
```

### Step 2: Execute

Run headless with `stream-json` output for structured monitoring. When the
Ollama endpoint is local, the harness runs sandboxed (macOS Seatbelt / Docker);
when remote, the sandbox is skipped (issue #749: Docker network namespace cannot
reach Tailscale/host-only interfaces) and the execution fence + overrun
verification carry the safety boundary. `yolo` approval prevents the headless
run from blocking on an interactive confirmation; bash `timeout` bounds a
runaway or stalled run (exit code 124 when exceeded - Qwen Code CLI has no
native wall-time flag).

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_FILE="/tmp/qwen-exec-${TIMESTAMP}.jsonl"

timeout 1800 qwen \
    --openai-base-url "$QWEN_ENDPOINT/v1" \
    --openai-api-key ollama \
    --auth-type openai \
    -m "$QWEN_MODEL" \
    --output-format stream-json \
    --approval-mode yolo \
    $SANDBOX_FLAG \
    "$PROMPT" < /dev/null 2>&1 | tee "$OUTPUT_FILE"   # </dev/null: non-TTY EOF so the harness never blocks reading stdin

QWEN_EXIT=$?
```

(The `--openai-api-key` value is a placeholder; Ollama ignores it. No cloud
API key is involved.)

### Step 3: Monitor and Report

**While it runs**, parse the JSONL stream and report progress: each line is a
JSON message with a `type` field (system/init metadata, assistant messages,
tool events, and a final `result` message carrying stats). Report file changes,
agent messages, and errors as they stream. Expect ~15-20 tok/s generation; a
substantial task can take several minutes per turn, and a thinking-enabled
model spends minutes reasoning before its first edit - the stream shows
liveness either way.

### Step 4: Summary

```bash
if [ "$QWEN_EXIT" -ne 0 ]; then
    echo ""
    echo "Qwen execution failed (exit code: $QWEN_EXIT)"
    if [ "$QWEN_EXIT" -eq 124 ]; then
        echo "(exit 124 = timeout exceeded - the run stalled or the task is too big)"
    fi
    echo "Output saved to: $OUTPUT_FILE"
    exit 1
fi

echo ""
echo "=== Changes ==="
git diff --stat 2>/dev/null || echo "(not a git repo or no changes)"
echo ""
echo "=== Diff ==="
git diff 2>/dev/null || echo "(no diff available)"
```

Report:

```
Qwen Exec Complete

  Prompt:    "{prompt summary}"
  Model:     {QWEN_MODEL} (local via Ollama)
  Duration:  {time}
  Changes:   {N} files modified (+{added} -{removed})
  Output:    {output_file}

Review the changes above. Use git add/commit to keep them,
or git checkout -- . to discard.
```

## Notes

- Runs in the CURRENT directory (not a worktree) - changes are applied directly
- When the Ollama endpoint is local (localhost/127.0.0.1/::1), the sandbox
  (Seatbelt/Docker) blocks writes outside the working directory. When remote
  (`QWEN_OLLAMA_URL` points at another machine), the sandbox is skipped because
  Docker's network namespace cannot reach Tailscale/host-only interfaces (issue
  #749). Shell commands the model runs retain network access in both modes, so
  the execution-fence + overrun-verification pattern from `/qwen:auto` still
  applies for anything beyond quick tasks
- JSONL output is saved to /tmp for later inspection
- No automatic commit - user reviews and commits manually
- For full issue lifecycle with review and quality gates, use `/qwen:auto`
- A local 27B model needs explicit, tightly scoped prompts; for broad or subtle tasks prefer `/codex:exec` or direct Claude implementation
