---
description: One-shot Codex execution in current directory with JSONL monitoring
allowed-tools: Bash(codex:*), Bash(git:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(tail:*), Bash(wc:*), Bash(test:*), Bash(pwd), Bash(tee:*)
---

# Codex Exec: One-Shot Codex Execution

Run Codex CLI in the current directory with JSONL monitoring.
For quick tasks without the full issue lifecycle.

## Arguments

- `PROMPT` (required): The task prompt for Codex (e.g., `"Add input validation to the login form"`)

## Instructions

When the user invokes `/codex:exec <PROMPT>`, perform these steps:

### Step 1: Verify Codex Availability

```bash
if ! command -v codex &>/dev/null; then
    echo "ERROR: Codex CLI not found."
    echo "Install with: npm install -g @openai/codex"
    echo "Then configure: codex login"
    exit 1
fi

CODEX_VERSION=$(codex --version 2>/dev/null || echo "unknown")
echo "Codex CLI: $CODEX_VERSION"
echo "Working directory: $(pwd)"
```

### Step 2: Execute Codex

Run Codex with JSONL output for structured monitoring:

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_FILE="/tmp/codex-exec-${TIMESTAMP}.jsonl"

codex exec \
    --json \
    --sandbox danger-full-access \
    "$PROMPT" 2>&1 | tee "$OUTPUT_FILE"

CODEX_EXIT=$?
```

### Step 3: Monitor and Report

**While Codex runs**, parse the JSONL stream and report:

- **Plan steps:** What Codex plans to do
- **File changes:** Which files are being created or modified
- **Messages:** Agent reasoning and progress
- **Errors:** Any failures during execution

### Step 4: Summary

After Codex completes:

```bash
if [ "$CODEX_EXIT" -ne 0 ]; then
    echo ""
    echo "Codex execution failed (exit code: $CODEX_EXIT)"
    echo "Output saved to: $OUTPUT_FILE"
    exit 1
fi

# Show changes
echo ""
echo "=== Changes ==="
git diff --stat 2>/dev/null || echo "(not a git repo or no changes)"
echo ""
echo "=== Diff ==="
git diff 2>/dev/null || echo "(no diff available)"
```

Report:

```
Codex Exec Complete

  Prompt:    "{prompt summary}"
  Duration:  {time}
  Changes:   {N} files modified (+{added} -{removed})
  Output:    {output_file}

Review the changes above. Use git add/commit to keep them,
or git checkout -- . to discard.
```

## Notes

- Runs in the CURRENT directory (not a worktree) - changes are applied directly
- Uses `--sandbox danger-full-access` - Codex can run any commands
- JSONL output is saved to /tmp for later inspection
- No automatic commit - user reviews and commits manually
- For full issue lifecycle with review and quality gates, use `/codex:auto`
