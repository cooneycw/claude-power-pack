---
description: Codex Orchestration commands overview
---

# Codex Orchestration Commands

Claude Code acts as supervisor/reviewer while Codex CLI implements features.
Cross-model implementation and review - Claude manages the workflow, Codex writes the code.

## Available Commands

| Command | Description |
|---------|-------------|
| `/codex:auto <ISSUE>` | Full issue lifecycle delegated to Codex - worktree, implement, review, quality gates, PR |
| `/codex:exec <PROMPT>` | One-shot Codex execution in current directory with JSONL monitoring |
| `/codex:ask <QUESTION>` | Delegate a read-only question to Codex and relay its answer (network opt-in on request) |
| `/codex:status` | Check Codex CLI installation, config, and readiness |
| `/codex:help` | This help overview |

## Architecture

```
Claude Code (supervisor)            Codex CLI (implementer)
  1. Read GH issue
  2. Create worktree + branch
  3. Build prompt from issue     --> 4. codex exec --json -C <worktree>
  5. Monitor JSONL stream        <-- 6. Plan, code, test
  7. Review Codex's diff
  8. Run quality gates (lint/test/security)
  9. If gates fail, re-prompt   --> 10. Fix with error context (max 2 retries)
  11. Commit, push, create PR
```

## Quick Start

```bash
# Check if Codex is ready
/codex:status

# Run a quick one-shot task
/codex:exec "Add input validation to the login form"

# Ask Codex a read-only question (no file changes)
/codex:ask "What does lib/cicd/config.py validate, and where are its tests?"

# Full issue lifecycle
/codex:auto 42
```

## Prerequisites

- **Codex CLI**: `npm install -g @openai/codex`
- **OpenAI API key**: `codex login` or set `OPENAI_API_KEY`
- **Verify**: `codex doctor`

## How It Differs From /flow:auto

| Aspect | `/flow:auto` | `/codex:auto` |
|--------|-------------|---------------|
| Implementer | Claude Code | Codex CLI |
| Reviewer | (self) | Claude Code (cross-model) |
| Sandbox | N/A | `danger-full-access` (worktree) |
| Fix loop | Manual | Automatic re-prompt (max 2) |
| Monitoring | Direct | JSONL event stream |

## Installation

Run `/cpp:init` and select **Tier 5 (Codex)** to:
1. Verify Codex CLI installation
2. Run `codex doctor`
3. Verify OpenAI API key
4. Optionally register CPP MCP servers with Codex

Or install manually:
```bash
npm install -g @openai/codex
codex login
codex doctor
```

## Notes

- Codex runs with `--sandbox danger-full-access` - safe in disposable worktrees
- `--json` flag provides structured JSONL output for monitoring
- Cross-model review catches issues that single-model review might miss
- Quality gate fix loop re-prompts Codex with error context (max 2 retries)
- All worktree cleanup follows the same safe patterns as `/flow:auto`
