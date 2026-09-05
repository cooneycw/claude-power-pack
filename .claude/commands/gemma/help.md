---
description: Local Gemma orchestration commands overview
---

# Gemma Orchestration Commands (Local Model)

Claude Code acts as supervisor/reviewer while a locally hosted Gemma 4 model
implements features. Same supervision architecture as `/codex:*` and `/qwen:*`,
but the implementer runs on a local GPU box via Ollama: zero API cost, full
privacy, and available to every machine on the tailnet/LAN.

## Available Commands

| Command | Description |
|---------|-------------|
| `/gemma:auto <ISSUE>` | Full lifecycle for an existing repo with a filed issue - worktree, implement, review, quality gates, PR |
| `/gemma:exec <PROMPT>` | Any task in the current directory - no repo or issue needed, and no automatic commit |
| `/gemma:status` | Check Ollama server, model, OpenCode harness, agent profile, and tool-calling readiness |
| `/gemma:help` | This help overview |

## Architecture

```
Claude Code (supervisor)            Local Gemma 4 via OpenCode harness
  1. Read GH issue
  2. Create worktree + branch
  3. Build prompt from issue     --> 4. opencode run --format json
  5. Monitor JSONL stream        <--    -m gemma-ollama/gemma4-code (served by Ollama)
  7. Review Gemma's diff               6. Plan, code, test (25-39 tok/s decode)
  8. Run quality gates (lint/test/security)
  9. If gates fail, re-prompt   --> 10. Fix with error context (max 2 retries)
  11. Commit, push, create PR
```

## Serving Stack

- **Model:** `gemma4-code:latest` - built from Google's `gemma4:31b-it-qat`
  (the quantization-aware-training build, ~18 GB) with the context window
  raised to 64K:
  ```bash
  ollama pull gemma4:31b-it-qat
  printf 'FROM gemma4:31b-it-qat\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.2\n' > /tmp/Modelfile.gemma4-code
  ollama create gemma4-code -f /tmp/Modelfile.gemma4-code
  ```
  **Why raise `num_ctx`:** Ollama's 32K default silently truncates long agent
  transcripts mid-run - the model does not error, it just loses the beginning
  of its own session. After creating the tag, confirm `ollama ps` still reports
  `100% GPU`; the reference box has roughly 3 GB of VRAM headroom at 64K, and a
  single layer spilling to CPU collapses throughput.
- **Server:** Ollama on the GPU host. The reference deployment
  (proxVMgemma23, RTX 3090 Ti) binds Ollama to `127.0.0.1` and exposes it to the
  tailnet with `tailscale serve --tcp 11434`, so the port is never on the LAN.
  systemd override: `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
  `OLLAMA_KEEP_ALIVE=-1` (keep the model resident; a 18 GB reload costs more
  than the idle VRAM).
- **Harness:** OpenCode (`npm install -g opencode-ai`) drives the model
  agentically. It is headless-scriptable (`opencode run --format json`), takes
  an explicit `--dir`, speaks the native Ollama API through the `ai-sdk-ollama`
  provider package, and has a config-level permission system that CPP uses as
  the mechanical fence. No cloud API key is used anywhere in this path.

### Measured performance vs. the Qwen lane

| | Gemma lane (RTX 3090 Ti) | Qwen lane (M1 Max) |
|---|---|---|
| Decode | 25-39 tok/s | 10-12 tok/s |
| Prefill @ 6K prompt | ~1,390 tok/s | ~86 tok/s |

Prefill is the difference that changes how the lane feels: a large-context turn
starts almost immediately rather than after a minute of ingestion.

### GPU exclusivity (reference deployment)

proxVMgemma23 shares its GPU claim with VMs 102/139 on the same host, and only
one may hold the card at a time. So `/gemma:status` reporting NOT READY can be a
scheduling fact rather than a broken install. Every probe in the `/gemma:*`
commands carries `--max-time` so an unavailable box fails fast instead of
hanging.

## Never `/v1` - Always Native `/api/chat`

This is the single most important design constraint in the lane, and it is not
a preference.

Ollama exposes two APIs: its own native `/api/chat`, and an OpenAI-compatible
`/v1` shim. OpenCode's own documented default for Ollama is the `/v1` shim via
`@ai-sdk/openai-compatible`. **That path is unusable for agentic work:**

- `/v1` drops streaming `tool_calls` delta chunks (long-standing, still open).
- `/v1` silently discards tool calls once the system prompt exceeds roughly
  1,600 tokens (ollama/ollama#14958).

An agentic harness system prompt is always past that threshold - OpenCode's
measures near 6,900 tokens. The failure mode is the dangerous kind: no error,
no warning, just a model that answers in plausible prose and never edits a
file. A short curl smoke test passes on both paths, so it proves nothing.

CPP therefore pins the `ai-sdk-ollama` package, which speaks native
`/api/chat`, and `/gemma:status` Step 4 guards the choice by running a REAL
`opencode run` with a forced tool call - inheriting the full system prompt, and
so actually exercising the failure. Do not "simplify" that check into a bare
API call, and do not switch the provider to `@ai-sdk/openai-compatible` because
upstream docs suggest it.

## Configuration

Both blocks live in `~/.config/opencode/opencode.json`. CPP ships them as
`templates/opencode-gemma.json`; `/cpp:init` Tier 7 installs them.

```json
{
  "provider": {
    "gemma-ollama": {
      "npm": "ai-sdk-ollama",
      "name": "Gemma (native Ollama API)",
      "options": { "baseURL": "{env:GEMMA_OLLAMA_URL}" },
      "models": { "gemma4-code": { "name": "Gemma 4 Code (64K ctx)" } }
    }
  },
  "agent": {
    "gemma-implementer": {
      "mode": "primary",
      "model": "gemma-ollama/gemma4-code",
      "temperature": 0.2,
      "permission": {
        "external_directory": "deny",
        "bash": { "*": "allow", "git commit*": "deny", "git push*": "deny", "gh *": "deny", "make deploy*": "deny" }
      }
    }
  }
}
```

`{env:GEMMA_OLLAMA_URL}` is OpenCode's environment substitution, resolved when
`opencode` starts - which is why the `/gemma:*` commands export
`GEMMA_OLLAMA_URL` in the same shell call that invokes the harness rather than
hardcoding a URL into the config. One config file then works on the serving
machine and on every consumer machine.

`ai-sdk-ollama` is resolved by OpenCode on first use rather than vendored. On a
fresh, offline, or proxied machine that resolution can fail, and it surfaces as
a *provider* error rather than a missing-package error - `/gemma:status` Step 3
names this explicitly so the message is not misread.

## The Mechanical Fence

OpenCode has no `--sandbox` flag: there is no container or Seatbelt profile to
turn on. What it has instead is a permission system in config, and CPP uses it
as the fence. The `gemma-implementer` agent denies:

- history- and ref-modifying git (`commit`, `push`, `reset`, `rebase`, `merge`,
  `checkout`, `switch`, `branch`, `tag`, `worktree`, `stash`)
- every `gh` command
- `make deploy*`, `make docker*`, `docker*`, `kubectl*`, `terraform*`
- `webfetch` and `websearch`
- `external_directory` - writes outside the directory the run was started in

A denied call returns to the model as a tool error, so it adapts and keeps
working rather than crashing.

**This is structurally better than the Qwen lane's sandbox**, for one specific
reason: issue #749 forced `/qwen:auto` to disable its Docker sandbox whenever
`QWEN_OLLAMA_URL` points at a remote machine, because a container's network
namespace cannot reach Tailscale interfaces. Remote serving is the normal case,
so that layer is off exactly when it is most wanted. A config-level rule has no
network dependency and holds identically either way.

It is not a replacement for the other two layers. The textual execution fence
still ships at the top of every prompt (a rule can block a command; only prose
can tell a model not to follow instructions it reads inside a repo file), and
post-execution overrun verification still runs - because a fence you never
audit is a fence you are only assuming.

## Using the Model From Other Machines

```bash
export GEMMA_OLLAMA_URL=http://proxvmgemma23:11434    # or the tailnet IP
```

That is the whole remote setup. `/gemma:auto`, `/gemma:exec`, and
`/gemma:status` all read it; unset, they default to `http://127.0.0.1:11434`.
The plain HTTP API works from anywhere on the tailnet too:

```bash
export OLLAMA_HOST=http://proxvmgemma23:11434   # ollama CLI
```

## Quick Start

Choose by precondition, not task size:

- `/gemma:auto <ISSUE>` - an EXISTING repo with a FILED issue. Creates a
  worktree and runs the full lifecycle through review, quality gates, and PR.
- `/gemma:exec <PROMPT>` - anything else, including a brand-new empty
  directory. Runs in the current directory with no repo or issue required and
  no automatic commit.

```bash
# Check if the stack is ready (includes a real tool-calling smoke test)
/gemma:status

# Run a quick one-shot task
/gemma:exec "Add input validation to the login form"

# Full issue lifecycle
/gemma:auto 42
```

## How It Differs From The Other Lanes

| Aspect | `/codex:auto` | `/qwen:auto` | `/gemma:auto` |
|--------|---------------|--------------|---------------|
| Implementer | Codex CLI (OpenAI cloud) | Local Qwen3.8-27B | Local Gemma 4 31B (QAT) |
| Harness | Codex CLI | Qwen Code CLI | OpenCode |
| Wire API | OpenAI | Ollama `/v1` | Ollama native `/api/chat` |
| Cost | OpenAI API tokens | Zero | Zero |
| Privacy | Code sent to OpenAI | Never leaves the network | Never leaves the network |
| Decode speed | Fast (cloud) | 10-12 tok/s | 25-39 tok/s |
| Mechanical fence | `workspace-write` | Seatbelt/Docker (off for remote, #749) | Permission profile (always on) |
| Escalation path | - | `/codex:auto` | `/qwen:auto` or `/codex:auto` |

## When To Use Which

- **`/gemma:auto`:** the default local lane when the GPU box is up - fastest
  local implementer, and a different model family from Qwen, which makes it the
  more useful second opinion.
- **`/qwen:auto`:** when the Gemma box does not hold the GPU claim, or when a
  code-specialized tag matters more than raw throughput.
- **`/codex:auto`:** broad or architecturally subtle issues, or after a local
  fix loop exhausts its retries.
- **`/flow:auto`:** when Claude itself should implement.

## Installation

Run `/cpp:init` and select **Tier 7 (Local Gemma)** to:
1. Verify/install the OpenCode CLI harness (no cloud API key needed)
2. Verify the Ollama server is reachable (local or via `GEMMA_OLLAMA_URL`)
3. Verify the model is present (create the 64K `gemma4-code` tag if on the serving machine)
4. Install the `gemma-ollama` provider and `gemma-implementer` agent profile
5. Run the tool-calling smoke test that proves the native-API path works

## Notes

- Defense in depth: textual execution fence + `gemma-implementer` permission
  profile + post-execution overrun verification. The middle layer is
  config-level, so it stays active for remote endpoints
- A local model wanders more than a frontier model - the fence and the Claude
  review step are mandatory, never skipped
- `GEMMA_MODEL` overrides the model tag; the OpenCode model reference is
  derived from it as `gemma-ollama/${GEMMA_MODEL%%:*}`, so a new tag needs a
  matching entry under the provider's `models` map
- Gemma 4 reports `completion`, `tools`, `thinking`, and `vision` capabilities
  to Ollama; the lane uses tools and completion. Unlike the Qwen 3 hybrids it
  does not emit thinking tokens by default, so there is no de-thinking
  workaround to configure
- The two local lanes are independent: different env vars, different harnesses,
  different config blocks. Running both on one machine requires no coordination
