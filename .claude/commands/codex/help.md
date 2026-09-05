---
description: Codex Orchestration commands overview
---

# Codex Orchestration Commands

Claude Code acts as supervisor/reviewer while Codex CLI implements features.
Cross-model implementation and review - Claude manages the workflow, Codex writes the code.

## Available Commands

| Command | Description |
|---------|-------------|
| `/codex:auto <ISSUE>` | Full lifecycle for an existing repo with a filed issue - worktree, implement, review, quality gates, PR |
| `/codex:exec <PROMPT>` | Any task in the current directory - no repo or issue needed, and no automatic commit |
| `/codex:ask <QUESTION>` | Delegate a read-only question to Codex and relay its answer (network opt-in on request) |
| `/codex:code_review [BASE]` | Codex reviews the current branch (read-only) and returns structured findings - used by `/flow:auto_codex` as the pre-PR review stage |
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

Choose by precondition, not task size:

- `/codex:auto <ISSUE>` - an EXISTING repo with a FILED issue. Creates a
  worktree and runs the full lifecycle through review, quality gates, and PR.
- `/codex:exec <PROMPT>` - anything else, including a brand-new empty
  directory. Runs in the current directory with no repo or issue required and
  no automatic commit.

```bash
# Check if Codex is ready
/codex:status

# Run a quick one-shot task
/codex:exec "Add input validation to the login form"

# Ask Codex a read-only question (no file changes)
/codex:ask "What does lib/cicd/config.py validate, and where are its tests?"

# Have Codex review the current branch before a PR exists
/codex:code_review origin/main

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
