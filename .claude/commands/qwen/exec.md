---
description: One-shot local Qwen execution in current directory with JSONL monitoring
allowed-tools: Bash(codex:*), Bash(ollama:*), Bash(git:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(curl:*), Bash(head:*), Bash(tail:*), Bash(wc:*), Bash(test:*), Bash(pwd), Bash(tee:*)
---

# Qwen Exec: One-Shot Local Qwen Execution

Run the local Qwen model (via the Codex CLI harness) in the current directory
with JSONL monitoring. For quick tasks without the full issue lifecycle.
Zero API cost - the model runs on local hardware through Ollama.

## Arguments

- `PROMPT` (required): The task prompt (e.g., `"Add input validation to the login form"`)

## Environment

- `QWEN_MODEL` (optional): Ollama model tag. Default: `qwen3.8-code:latest`.
- `QWEN_CODEX_PROFILE` (optional): Codex config profile for reaching a remote
  Qwen server; replaces the `--oss` flags when set (see `/qwen:help`).

## Instructions

When the user invokes `/qwen:exec <PROMPT>`, perform these steps:

### Step 1: Verify Availability

```bash
if ! command -v codex &>/dev/null; then
    echo "ERROR: Codex CLI not found (required as the local-model harness)."
    echo "Install with: npm install -g @openai/codex"
    exit 1
fi

QWEN_MODEL="${QWEN_MODEL:-qwen3.8-code:latest}"

if [ -z "$QWEN_CODEX_PROFILE" ]; then
    if ! curl -sf --max-time 5 http://127.0.0.1:11434/api/version > /dev/null; then
        echo "ERROR: Ollama not reachable on 127.0.0.1:11434. Run /qwen:status to diagnose."
        exit 1
    fi
fi

echo "Harness: $(codex --version 2>/dev/null)"
echo "Model:   $QWEN_MODEL"
echo "Working directory: $(pwd)"
```

### Step 2: Execute

Run with JSONL output for structured monitoring. Unlike `/codex:exec`, the
sandbox is **workspace-write** (not `danger-full-access`): a local model
warrants the tighter mechanical boundary.

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_FILE="/tmp/qwen-exec-${TIMESTAMP}.jsonl"

if [ -n "$QWEN_CODEX_PROFILE" ]; then
    codex exec \
        --json \
        --profile "$QWEN_CODEX_PROFILE" \
        --sandbox workspace-write \
        "$PROMPT" < /dev/null 2>&1 | tee "$OUTPUT_FILE"   # </dev/null: non-TTY EOF so codex never blocks reading stdin
else
    codex exec \
        --json \
        --oss --local-provider ollama \
        -m "$QWEN_MODEL" \
        --sandbox workspace-write \
        "$PROMPT" < /dev/null 2>&1 | tee "$OUTPUT_FILE"   # </dev/null: non-TTY EOF so codex never blocks reading stdin
fi

CODEX_EXIT=$?
```

### Step 3: Monitor and Report

**While it runs**, parse the JSONL stream and report plan steps, file changes,
messages, and errors. A "Model metadata ... not found. Defaulting to fallback
metadata" item is benign for Ollama-served models. Expect ~15-20 tok/s
generation; a substantial task can take several minutes per turn.

### Step 4: Summary

```bash
if [ "$CODEX_EXIT" -ne 0 ]; then
    echo ""
    echo "Qwen execution failed (exit code: $CODEX_EXIT)"
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
- Uses `--sandbox workspace-write` - the model cannot reach the network or escape the directory
- JSONL output is saved to /tmp for later inspection
- No automatic commit - user reviews and commits manually
- For full issue lifecycle with review and quality gates, use `/qwen:auto`
- A local 27B model needs explicit, tightly scoped prompts; for broad or subtle tasks prefer `/codex:exec` or direct Claude implementation
