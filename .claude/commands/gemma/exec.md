---
description: One-shot local Gemma execution in current directory with JSONL monitoring
allowed-tools: Bash(opencode:*), Bash(ollama:*), Bash(git:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(curl:*), Bash(head:*), Bash(tail:*), Bash(wc:*), Bash(test:*), Bash(pwd), Bash(~/.claude/scripts/delegated-run-check.sh:*)
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

**The redirect is load-bearing, not a style choice (issue #798).** This was
`... | tee "$OUTPUT_FILE"`, and `$?` after a pipeline is the status of the LAST
command - `tee` - not the CLI. With `pipefail` set nowhere, a run killed by the
1800s `timeout` reported success and the "exit 124 = timeout" branch below was
unreachable:

```
$ ( timeout 1 sleep 5 2>&1 | tee /dev/null; echo $? )
0        # should be 124
$ ( timeout 1 sleep 5 > /dev/null 2>&1; echo $? )
124
```

Writing straight to the file costs nothing - the run is monitored by reading
the JSONL, not by watching the terminal - and `$?` then belongs to `opencode`.
Keep the capture in the SAME fenced block as the invocation; in a separate
block it is a separate shell and reads whatever ran last there instead.

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_FILE="/tmp/gemma-exec-${TIMESTAMP}.jsonl"

GEMMA_OLLAMA_URL="$GEMMA_ENDPOINT" timeout 1800 opencode run \
    --dir "$(pwd)" \
    -m "$GEMMA_MODEL_REF" \
    --agent gemma-implementer \
    --format json \
    --auto \
    "$PROMPT" < /dev/null > "$OUTPUT_FILE" 2>&1   # </dev/null: non-TTY EOF so the harness never blocks reading stdin

GEMMA_EXIT=$?
echo "opencode exited $GEMMA_EXIT; output: $OUTPUT_FILE"
tail -40 "$OUTPUT_FILE"
```

(No API key is involved anywhere in this path. The provider talks to Ollama's
native `/api/chat` endpoint through the `ai-sdk-ollama` package - never the
OpenAI-compatible `/v1` path, which drops tool calls on long system prompts.
See `/gemma:help`.)

### Step 3: Monitor and Report

Read the JSONL stream from `$OUTPUT_FILE` and report progress. Each line is one
JSON object with a top-level `type`:

| `type` | Meaning |
|--------|---------|
| `step_start` | A new agent turn began |
| `tool_use` | A tool call - `part.tool` names it, `part.state.status` is `completed`, `error`, or `running` |
| `text` | Model prose addressed to the user |
| `step_finish` | Turn ended; `part.tokens` carries input/output counts and `part.reason` the stop reason |

Report file changes, agent messages, and errors. A denied command surfaces as a
`tool_use` with `state.status: "error"` and a rule-denial message - that is the
fence working, not a failure.

Expect 25-39 tok/s decode on the reference RTX 3090 Ti (roughly triple the Qwen
lane) with prefill near 1,390 tok/s at a 6K prompt, so a substantial task still
takes minutes per turn. The stream shows liveness.

### Step 4: Verdict and Summary

**The exit code is necessary and never sufficient (issue #798).** The Qwen lane
was verified reporting `EXIT=0` / `is_error: false` over a run whose only
evidence of failure was `[API Error: ...]` inside its terminal payload. That
behaviour was NOT verified for OpenCode, and this check is written defensively
rather than on the assumption that it is absent here. Hand both the code and
the payload to the audited helper.

**Invoke it BARE, with LITERAL values (issue #798 review).** Two reasons, and
both were learned the hard way. This block is a DIFFERENT shell from the one
above: `$GEMMA_EXIT` and the output path are not exported and would arrive
empty, so the helper would exit 2 without a verdict - the very separate-shell
defect this document fixes, reproduced one level up. And a helper call carrying
variable expansions cannot match the `Bash(~/.claude/scripts/...:*)` allowlist
prefix, so it would prompt on every run. Substitute the exit code and path the
block above printed, exactly as Step 1's verify gate does:

```bash
~/.claude/scripts/delegated-run-check.sh /tmp/gemma-exec-20260907-120000.jsonl 124 --lane gemma
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
`no-tool-use`, ...):

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
```

On `DELEGATED_RUN_STATUS: failure` report the signals and the
`DELEGATED_RUN_DETAIL` line verbatim and **STOP** - do not present a diff as
though the run had produced it. A `no-tool-use` signal does not by itself fail
an `exec` run, but on this lane it is the signature of the ollama/ollama#14958
`/v1` tool-call-drop bug: run `/gemma:status`, whose Step 4 smoke test tests
exactly that, before blaming the prompt.

**And on `success`, read `DELEGATED_RUN_TOOL_ERRORS` before you believe it
(issue #836).** The verdict answers *"did the delegated process run cleanly?"*
It is routinely read as *"did the delegated work happen?"*, and those come apart
exactly here: a tool call denied by a permission fence still counts as
`tool_use`, leaves the payload well formed and the exit code 0, so a run whose
every command was refused reports `success`. One did, and returned a fabricated
empty inventory that nothing downstream could have questioned.

A non-zero count is **not** a failed run - a denied call is the fence working as
designed, and making it fatal is a defect that was already shipped and reverted.
It is the one fact that tells you to go and look: read the payload, or check the
postcondition the work was supposed to establish, before reporting the result as
done. The line is always emitted, `0` included, so `0` means "checked, none"
rather than "not checked".

```bash
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
