---
description: One-shot local Gemma execution in current directory with JSONL monitoring
allowed-tools: Bash(opencode:*), Bash(ollama:*), Bash(git:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(curl:*), Bash(head:*), Bash(tail:*), Bash(wc:*), Bash(test:*), Bash(pwd), Bash(tee:*)
---

# Gemma Exec: One-Shot Local Gemma Execution

Run the local Gemma 4 model (via the OpenCode harness) in the current directory
with JSONL monitoring. For quick tasks without the full issue lifecycle. Zero
API cost - the model runs on local GPU hardware through Ollama.

This is also the greenfield command: it needs no repo or issue and works in a
brand-new empty directory. `/gemma:auto` is narrower and requires both an
existing git checkout and a filed issue.

## Arguments

- `PROMPT` (required): The task prompt (e.g., `"Add input validation to the login form"`)

## Environment

- `GEMMA_MODEL` (optional): Ollama model tag. Default: `gemma4-code:latest`.
  The OpenCode model reference is derived from it as
  `gemma-ollama/${GEMMA_MODEL%%:*}`.
- `GEMMA_OLLAMA_URL` (optional): base URL of the Ollama server for remote
  serving machines (e.g., `http://proxvmgemma23:11434`). Default:
  `http://127.0.0.1:11434`. It must be exported BEFORE `opencode` runs: the
  provider's `baseURL` in `~/.config/opencode/opencode.json` is the literal
  `{env:GEMMA_OLLAMA_URL}`, resolved by OpenCode at invocation time.

## Instructions

When the user invokes `/gemma:exec <PROMPT>`, perform these steps:

### Step 1: Verify Availability

```bash
if ! command -v opencode &>/dev/null; then
    echo "ERROR: OpenCode CLI not found (required as the local-model harness)."
    echo "Install with: npm install -g opencode-ai"
    exit 1
fi

GEMMA_MODEL="${GEMMA_MODEL:-gemma4-code:latest}"
GEMMA_ENDPOINT="${GEMMA_OLLAMA_URL:-http://127.0.0.1:11434}"
GEMMA_MODEL_REF="gemma-ollama/${GEMMA_MODEL%%:*}"

if ! curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/version" > /dev/null; then
    echo "ERROR: Ollama not reachable at $GEMMA_ENDPOINT. Run /gemma:status to diagnose."
    echo "Remote serving machine: set GEMMA_OLLAMA_URL=http://<serving-host>:11434"
    echo "(On the reference server the GPU claim is shared with other VMs - an"
    echo " unreachable endpoint can simply mean another VM holds the card.)"
    exit 1
fi

echo "Harness: opencode $(opencode --version 2>/dev/null)"
echo "Model:   $GEMMA_MODEL_REF via $GEMMA_ENDPOINT (native /api/chat)"
echo "Working directory: $(pwd)"
```

**The mechanical fence is the agent profile, not a sandbox.** OpenCode has no
`--sandbox` flag - there is no container or Seatbelt equivalent to the one
`/qwen:exec` uses. What replaces it is `--agent gemma-implementer`, whose
`permission` block in `~/.config/opencode/opencode.json` denies `git commit`,
`git push`, every `gh` command, deploy/docker/kubectl/terraform, and writes
outside the working directory (`external_directory: deny`). Denied calls come
back to the model as a tool error, so it keeps working within the boundary
instead of dying.

This profile is REQUIRED, not decorative. Verify it before running - a missing
profile silently downgrades the run to the textual fence alone:

```bash
if ! grep -q '"gemma-implementer"' ~/.config/opencode/opencode.json 2>/dev/null; then
    echo "ERROR: agent profile 'gemma-implementer' is not configured."
    echo "It carries the mechanical fence (deny rules for git/gh/deploy and"
    echo "out-of-directory writes). Install it from templates/opencode-gemma.json"
    echo "or re-run /cpp:init and select Tier 7. See /gemma:help."
    exit 1
fi
```

Unlike the Qwen lane, this fence needs no adjustment for a remote endpoint: it
is config-level, not network-level, so it does not have the issue #749 problem
where a Docker sandbox could not reach a Tailscale-served model and had to be
switched off entirely.

### Step 2: Execute

Run headless with `--format json` for structured monitoring. `--auto`
auto-approves permissions that are not explicitly denied, which is what keeps
an unattended run from blocking on an approval prompt - the profile's `deny`
rules still apply and are exactly the ones that matter. Bash `timeout` bounds a
runaway or stalled run (exit code 124 when exceeded).

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_FILE="/tmp/gemma-exec-${TIMESTAMP}.jsonl"

GEMMA_OLLAMA_URL="$GEMMA_ENDPOINT" timeout 1800 opencode run \
    --dir "$(pwd)" \
    -m "$GEMMA_MODEL_REF" \
    --agent gemma-implementer \
    --format json \
    --auto \
    "$PROMPT" < /dev/null 2>&1 | tee "$OUTPUT_FILE"   # </dev/null: non-TTY EOF so the harness never blocks reading stdin

GEMMA_EXIT=$?
```

(No API key is involved anywhere in this path. The provider talks to Ollama's
native `/api/chat` endpoint through the `ai-sdk-ollama` package - never the
OpenAI-compatible `/v1` path, which drops tool calls on long system prompts.
See `/gemma:help`.)

### Step 3: Monitor and Report

**While it runs**, parse the JSONL stream and report progress. Each line is one
JSON object with a top-level `type`:

| `type` | Meaning |
|--------|---------|
| `step_start` | A new agent turn began |
| `tool_use` | A tool call - `part.tool` names it, `part.state.status` is `completed`, `error`, or `running` |
| `text` | Model prose addressed to the user |
| `step_finish` | Turn ended; `part.tokens` carries input/output counts and `part.reason` the stop reason |

Report file changes, agent messages, and errors as they stream. A denied
command surfaces as a `tool_use` with `state.status: "error"` and a rule-denial
message - that is the fence working, not a failure.

Expect 25-39 tok/s decode on the reference RTX 3090 Ti (roughly triple the Qwen
lane) with prefill near 1,390 tok/s at a 6K prompt, so a substantial task still
takes minutes per turn. The stream shows liveness.

### Step 4: Summary

```bash
if [ "$GEMMA_EXIT" -ne 0 ]; then
    echo ""
    echo "Gemma execution failed (exit code: $GEMMA_EXIT)"
    if [ "$GEMMA_EXIT" -eq 124 ]; then
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
Gemma Exec Complete

  Prompt:    "{prompt summary}"
  Model:     {GEMMA_MODEL} (local via Ollama, native /api/chat)
  Duration:  {time}
  Changes:   {N} files modified (+{added} -{removed})
  Output:    {output_file}

Review the changes above. Use git add/commit to keep them,
or git checkout -- . to discard.
```

## Notes

- Runs in the CURRENT directory (not a worktree) - changes are applied directly.
  `--dir` is passed explicitly rather than relying on the inherited cwd
- The mechanical boundary is the `gemma-implementer` permission profile, not a
  sandbox: OpenCode ships no `--sandbox` flag. Because the profile is
  config-level it works identically for a local or a remote endpoint, which is
  the one place this lane is structurally safer than `/qwen:exec` (issue #749
  forced that lane to drop its sandbox for remote Ollama servers)
- The profile denies git/gh/deploy commands but shell commands it does allow
  retain network access, so the textual execution fence from `/gemma:auto`
  still applies for anything beyond quick tasks
- JSONL output is saved to /tmp for later inspection
- No automatic commit - the user reviews and commits manually
- For a full issue lifecycle with review and quality gates, use `/gemma:auto`
- A local 31B model needs explicit, tightly scoped prompts; for broad or subtle
  tasks prefer `/codex:exec` or direct Claude implementation
