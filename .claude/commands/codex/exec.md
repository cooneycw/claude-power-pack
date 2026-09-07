---
description: One-shot Codex execution in current directory with JSONL monitoring
allowed-tools: Bash(codex:*), Bash(git:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(tail:*), Bash(wc:*), Bash(test:*), Bash(pwd), Bash(~/.claude/scripts/delegated-run-check.sh:*)
---

# Codex Exec: One-Shot Codex Execution

Run Codex CLI in the current directory with JSONL monitoring.
For quick tasks without the full issue lifecycle.

This is also the greenfield command: it needs no repo or issue and works in a
brand-new empty directory. `/codex:auto` is narrower and requires both an
existing git checkout and a filed issue.

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

Run Codex with JSONL output for structured monitoring.

**The redirect is load-bearing, not a style choice (issue #798).** This was
`... | tee "$OUTPUT_FILE"`, and `$?` after a pipeline is the status of the LAST
command - `tee` - not the CLI. With `pipefail` set nowhere, a killed or failed
run reported success:

```
$ ( timeout 1 sleep 5 2>&1 | tee /dev/null; echo $? )
0        # should be 124
$ ( timeout 1 sleep 5 > /dev/null 2>&1; echo $? )
124
```

Writing straight to the file costs nothing - the run is monitored by reading
the JSONL, not by watching the terminal - and `$?` then belongs to `codex`.
Keep the capture in the SAME fenced block as the invocation; in a separate
block it is a separate shell and reads whatever ran last there instead.

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_FILE="/tmp/codex-exec-${TIMESTAMP}.jsonl"

codex exec \
    --json \
    --sandbox danger-full-access \
    "$PROMPT" < /dev/null > "$OUTPUT_FILE" 2>&1   # </dev/null: non-TTY EOF so codex never blocks reading stdin

CODEX_EXIT=$?
echo "codex exited $CODEX_EXIT; output: $OUTPUT_FILE"
tail -40 "$OUTPUT_FILE"
```

### Step 3: Monitor and Report

Read the JSONL stream from `$OUTPUT_FILE` and report:

- **Plan steps:** What Codex plans to do
- **File changes:** Which files are being created or modified
- **Messages:** Agent reasoning and progress
- **Errors:** Any failures during execution

### Step 4: Verdict and Summary

**The exit code is necessary and never sufficient (issue #798).** The Qwen lane
was verified reporting `EXIT=0` / `is_error: false` over a run whose only
evidence of failure was `[API Error: ...]` inside its terminal payload. That
behaviour was NOT verified for the Codex CLI, and this check is written
defensively rather than on the assumption that it is absent here. Hand both the
code and the payload to the audited helper.

**Invoke it BARE, with LITERAL values (issue #798 review).** Two reasons, and
both were learned the hard way. This block is a DIFFERENT shell from the one
above: `$CODEX_EXIT` and the output path are not exported and would arrive
empty, so the helper would exit 2 without a verdict - the very separate-shell
defect this document fixes, reproduced one level up. And a helper call carrying
variable expansions cannot match the `Bash(~/.claude/scripts/...:*)` allowlist
prefix, so it would prompt on every run. Substitute the exit code and path the
block above printed, exactly as Step 1's verify gate does:

```bash
~/.claude/scripts/delegated-run-check.sh /tmp/codex-exec-20260907-120000.jsonl 0 --lane codex
```

(Exit 127 - the helper family is not installed: fall back to
`${CLAUDE_PLUGIN_ROOT}/scripts/delegated-run-check.sh`, else the CPP-checkout
copy (either may prompt once); tell the user to run **`/flow:repair`** to
restore the prompt-free lane. If NO copy exists anywhere, treat the run as
UNASSESSABLE and stop - do NOT fall back to the exit code alone. On this lane
a clean exit is the documented shape of a FAILED run, so proceeding on it
restores the exact false green this check exists to remove.)

The helper prints `DELEGATED_RUN_STATUS: success|failure` and exits 1 on
failure, naming every signal it found (`timeout`, `api-error`, `output-empty`,
`no-turns`, ...). On failure report the signals and the `DELEGATED_RUN_DETAIL`
line verbatim and **STOP** - do not present a diff as though the run had
produced it. `no-tool-use` alone does not fail an `exec` run: a question can
legitimately be answered without touching a file.

Unlike the two local-model lanes this invocation carries no bash `timeout`, so
there is deliberately no `exit 124` branch here - a branch no invocation can
reach is the defect this issue was filed about, one level down. If a caller
wraps the run in `timeout`, the helper names the `timeout` signal on its own.

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
- For a read-only question (no file changes), use `/codex:ask`
