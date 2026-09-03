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
| `/qwen:auto <ISSUE>` | Full issue lifecycle delegated to local Qwen - worktree, implement, review, quality gates, PR |
| `/qwen:exec <PROMPT>` | One-shot local Qwen execution in current directory with JSONL monitoring |
| `/qwen:status` | Check Ollama server, model, and Codex harness readiness |
| `/qwen:help` | This help overview |

## Architecture

```
Claude Code (supervisor)            Local Qwen via Codex CLI harness
  1. Read GH issue
  2. Create worktree + branch
  3. Build prompt from issue     --> 4. codex exec --json --oss --local-provider ollama
  5. Monitor JSONL stream        <--    -m qwen3.8-code:latest (served by Ollama)
  7. Review Qwen's diff                6. Plan, code, test (~15-20 tok/s locally)
  8. Run quality gates (lint/test/security)
  9. If gates fail, re-prompt   --> 10. Fix with error context (max 2 retries)
  11. Commit, push, create PR
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
- **Harness:** Codex CLI (`npm install -g @openai/codex`) drives the model
  agentically. No OpenAI API key is used in `--oss` mode.

## Using the Model From Other Machines

The plain HTTP API works from anywhere that can reach the serving machine:

```bash
export OLLAMA_HOST=http://<serving-machine-tailscale-ip>:11434   # ollama CLI
# or OpenAI-compatible: base_url http://<ip>:11434/v1, any api_key string
```

For `/qwen:auto` and `/qwen:exec` on a REMOTE machine, the Codex harness needs
a config profile (Codex ignores OLLAMA_HOST). Add to `~/.codex/config.toml`:

```toml
[model_providers.qwen-local]
name = "Qwen on local network"
base_url = "http://<serving-machine-tailscale-ip>:11434/v1"
wire_api = "chat"

[profiles.qwen]
model_provider = "qwen-local"
model = "qwen3.8-code:latest"
```

Then set `QWEN_CODEX_PROFILE=qwen` before invoking `/qwen:auto` or `/qwen:exec`.

## Quick Start

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
| Cost | OpenAI API tokens | Zero (local hardware) |
| Privacy | Code sent to OpenAI | Code never leaves the network |
| Speed | Fast (cloud inference) | ~15-20 tok/s (Apple Silicon) |
| Capability | Frontier model | Strong 27B - needs tighter prompts, stricter review |
| Sandbox | `workspace-write` | `workspace-write` |
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
1. Verify/install the Codex CLI harness (no OpenAI key needed)
2. Verify the Ollama server is reachable (local or via `QWEN_OLLAMA_URL`)
3. Verify the model is present (pull/create if on the serving machine)
4. Optionally write the remote-access Codex profile
5. Optionally enable the always-on second opinion (mcp-second-opinion v2.3.0+)

## Notes

- Same defense-in-depth as `/codex:auto`: execution fence + `workspace-write` sandbox + overrun verification
- A local model wanders more than a frontier model - the fence and the Claude review step are mandatory, never skipped
- `QWEN_MODEL` overrides the model tag; any Ollama-served coding model works (e.g., `qwen3-coder:30b`)
- Expect minutes-per-turn pacing on the serving hardware; the JSONL stream shows liveness
