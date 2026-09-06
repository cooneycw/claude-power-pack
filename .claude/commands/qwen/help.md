---
description: Local Qwen orchestration commands overview
---

# Qwen Orchestration Commands (Local Model)

Claude Code acts as supervisor/reviewer while a locally hosted Qwen model
implements features. Same supervision architecture as `/codex:*`, but the
implementer runs on local hardware via Ollama: zero API cost, full privacy,
and available to every machine on the tailnet/LAN.

## Available Commands

| Command | Description |
|---------|-------------|
| `/qwen:auto <ISSUE>` | Full lifecycle for an existing repo with a filed issue - worktree, implement, review, quality gates, PR |
| `/qwen:exec <PROMPT>` | Any task in the current directory - no repo or issue needed, and no automatic commit |
| `/qwen:status` | Check Ollama server, model, and Qwen Code harness readiness |
| `/qwen:help` | This help overview |

## Architecture

```
Claude Code (supervisor)            Local Qwen via Qwen Code CLI harness
  1. Read GH issue
  2. Create worktree + branch
  3. Build prompt from issue
  4. GATE: stop for approval     --> 5. qwen --output-format stream-json
  6. Monitor JSONL stream        <--    -m qwen3.8-code:latest (served by Ollama)
  8. Review Qwen's diff                7. Plan, code, test (~15-20 tok/s locally)
  9. Run quality gates (lint/test/security)
  10. If gates fail, re-prompt  --> 11. Fix with error context (max 2 retries)
  12. Commit, push, create PR
```

## Serving Stack

- **Model:** `qwen3.8-code:latest` - Qwen3.8-27B (Q4_K_M GGUF, ~17 GB) with a
  64k context window, created from `qwen3.8:27b`:
  ```bash
  ollama pull qwen3.8:27b
  printf 'FROM qwen3.8:27b\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.7\nPARAMETER top_p 0.8\n' | ollama create qwen3.8-code -f -
  ```
- **Server:** Ollama bound to `0.0.0.0:11434` so LAN and Tailscale machines can
  use it. On macOS this is a launchd agent with `OLLAMA_HOST=0.0.0.0:11434`
  (plus `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
  `OLLAMA_KEEP_ALIVE=30m`).
- **Harness:** Qwen Code CLI (`npm install -g @qwen-code/qwen-code`, pin 0.23.0
  or later) drives the model agentically over Ollama's OpenAI-compatible
  endpoint. Built by the Qwen team, so Qwen 3 reasoning/thinking stream fields
  are parsed natively. No cloud API key is used - the `--openai-api-key` value
  is a placeholder that Ollama ignores.

### Why not the Codex CLI harness? (issue #745)

The original `/qwen:*` harness was `codex exec --oss --local-provider ollama`.
That path is retired:

- Codex deleted the chat-completions wire API at v0.95 (openai/codex#10157);
  `wire_api = "chat"` in any `~/.codex/config.toml` provider is now a hard
  startup error, which broke the previously documented remote profile recipe.
- `--oss` speaks Ollama's `/v1/responses` endpoint, where Qwen 3 thinking
  models hit an unfixed answer-swallowing bug (ollama/ollama#18187) and the
  thinking phase renders as an apparent indefinite hang.
- OpenAI closed remote-Ollama support as not-planned (openai/codex#8240) and
  the local-provider path regressed repeatedly through 2026.

Qwen Code CLI meets every harness requirement Codex covered: headless one-shot
mode, `stream-json` event output, an OS sandbox (macOS Seatbelt / Docker), and
first-class custom OpenAI-compatible endpoints.

## Thinking Tokens (read before changing models)

Qwen 3 hybrid models (including `qwen3.8`) emit reasoning/thinking tokens by
default. The Qwen Code harness parses them correctly, but they are slow on
local hardware (minutes of thinking at ~15-20 tok/s before any code appears):

- **Prefer a non-thinking coder tag** for implementation work when available
  (e.g. `qwen3-coder:30b`): Qwen3-Coder models never emit thinking blocks and
  are trained specifically for agentic coding.
- **Or lower the effort server-side:** Ollama's OpenAI-compatible endpoint
  accepts `reasoning_effort` (`"none"`, `"low"`, `"medium"`, `"high"`); the
  native API equivalent is `think: false`. Note the Qwen team's guidance that
  low effort on hybrid models degrades hard multi-step reasoning - for broad
  issues, escalate to `/codex:auto` rather than running a de-thinking hybrid.
- The `/no_think` soft prompt switch is unreliable on post-2507 Qwen models;
  do not depend on it.

## Using the Model From Other Machines

The plain HTTP API works from anywhere that can reach the serving machine:

```bash
export OLLAMA_HOST=http://<serving-machine-tailscale-ip>:11434   # ollama CLI
# or OpenAI-compatible: base_url http://<ip>:11434/v1, any api_key string
```

For `/qwen:auto` and `/qwen:exec` on a REMOTE machine, no SSH tunnel and no
harness config file are needed - set one environment variable:

```bash
export QWEN_OLLAMA_URL=http://<serving-machine-tailscale-ip>:11434
```

The commands derive the harness endpoint from it
(`$QWEN_OLLAMA_URL/v1`) and pass it via `--openai-base-url`. Unset, the
commands default to `http://127.0.0.1:11434`.

## Sandbox and Remote Endpoints (issue #749)

The Qwen Code CLI's `--sandbox` flag runs the model inside a Docker container
(Linux) or a Seatbelt profile (macOS) that blocks writes outside the working
directory. On Linux, Docker containers run in their own network namespace, so
they cannot reach Tailscale interfaces, LAN-only addresses, or other host-only
network endpoints.

**Automatic detection:** `/qwen:auto` and `/qwen:exec` parse `QWEN_OLLAMA_URL`
and decide at invocation time:

| Endpoint host | Sandbox | Rationale |
|---------------|---------|-----------|
| `127.0.0.1`, `localhost`, `::1` (or unset) | `--sandbox` enabled | Local server - Docker networking is fine |
| Anything else (e.g., a Tailscale IP) | `--sandbox` skipped | Docker network namespace cannot reach host-only interfaces |

When the sandbox is skipped, the two other safety layers remain active:

1. **Execution fence** - a textual constraint at the top of every prompt that
   forbids git/gh/deploy/infrastructure commands.
2. **Post-execution overrun verification** - automated checks that the model
   did not commit, push, create PRs, or escape its implementation-only boundary.

These layers are always present regardless of sandbox state and already carry
the network boundary (the sandbox never blocked network from shell commands the
model runs).

**Force override:** To force sandbox on for a remote endpoint (e.g., if Docker
is configured with `--network host`), set `QWEN_FORCE_SANDBOX=1`. To force
sandbox off for a local endpoint, set `QWEN_FORCE_SANDBOX=0`. The detection
only applies when the variable is unset.

## Quick Start

Choose by precondition, not task size:

- `/qwen:auto <ISSUE>` - an EXISTING repo with a FILED issue. Creates a
  worktree and runs the full lifecycle through review, quality gates, and PR.
  It STOPS after the Step 2 plan report and waits for approval before the model
  writes anything (Step 3/8). That pause has no bypass (issue #784): `--yes` /
  `--auto-approve` are recognized only to report that the gate is not skippable.
- `/qwen:exec <PROMPT>` - anything else, including a brand-new empty
  directory. Runs in the current directory with no repo or issue required and
  no automatic commit.

Then check CAPABILITY, which is a different axis from precondition (issue #783):

> **`/qwen:auto` cannot take `research` or `web` work.** The model runs under an
> IMPLEMENTATION-ONLY execution fence, so its deliverable is a source diff, not
> a finding; and this lane configures no retrieval tool, so a live-source
> question comes back answered from a local model's training data. Route both
> classes to `/flow:auto`. See "Capability contract" in `/qwen:auto`, or run
> `~/.claude/scripts/flow-driver-capability.sh show qwen:auto`.

```bash
# Check if the stack is ready
/qwen:status

# Run a quick one-shot task
/qwen:exec "Add input validation to the login form"

# Full issue lifecycle
/qwen:auto 42
```

## How It Differs From /codex:auto

| Aspect | `/codex:auto` | `/qwen:auto` |
|--------|---------------|--------------|
| Implementer | Codex CLI (OpenAI cloud) | Local Qwen3.8-27B via Ollama |
| Harness | Codex CLI | Qwen Code CLI |
| Cost | OpenAI API tokens | Zero (local hardware) |
| Privacy | Code sent to OpenAI | Code never leaves the network |
| Speed | Fast (cloud inference) | ~15-20 tok/s (Apple Silicon) |
| Capability | Frontier model | Strong 27B - needs tighter prompts, stricter review |
| Sandbox | `workspace-write` | Seatbelt/Docker sandbox (local endpoint) / skipped for remote (issue #749) |
| Escalation path | - | Falls back to `/codex:auto` when it struggles |

## When To Use Which

- **`/qwen:auto`:** well-scoped issues, mechanical changes, privacy-sensitive
  code, or when API budget matters. Overnight/batch work where speed is fine.
- **`/codex:auto`:** broad or architecturally subtle issues, or after the Qwen
  fix loop exhausts its retries.
- **`/flow:auto`:** when Claude itself should implement.

## Always-On Second Opinion

The external mcp-second-opinion server (v2.3.0+) carries a keyless `ollama`
provider with model key `qwen-local`, and its `ALWAYS_CONSULT_MODELS` config
(default: `qwen-local`) merges the local Qwen into EVERY second-opinion
consultation - both the multi-model fan-out and the Gemini-primary code
review (as `additional_opinions`). Zero cost, so it rides along on every
review. Server-side env knobs: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`,
`ALWAYS_CONSULT_MODELS` (empty string disables).

## Installation

Run `/cpp:init` and select **Tier 6 (Local Qwen)** to:
1. Verify/install the Qwen Code CLI harness (no cloud API key needed)
2. Verify the Ollama server is reachable (local or via `QWEN_OLLAMA_URL`)
3. Verify the model is present (pull/create if on the serving machine)
4. Optionally enable the always-on second opinion (mcp-second-opinion v2.3.0+)

## Notes

- Same defense-in-depth as `/codex:auto`: execution fence + sandbox + overrun verification. When `QWEN_OLLAMA_URL` is a remote endpoint, the sandbox is automatically skipped (issue #749) and the fence + overrun verification carry the full boundary
- A local model wanders more than a frontier model - the fence and the Claude review step are mandatory, never skipped
- `QWEN_MODEL` overrides the model tag; any Ollama-served coding model works (e.g., `qwen3-coder:30b`)
- Expect minutes-per-turn pacing on the serving hardware; the JSONL stream shows liveness
- The sandbox (Seatbelt/Docker) blocks writes outside the working directory but does NOT block network from shell commands the model runs - the execution fence plus post-run overrun verification cover that gap in all modes. `QWEN_FORCE_SANDBOX` overrides the automatic detection (1 = force on, 0 = force off)
