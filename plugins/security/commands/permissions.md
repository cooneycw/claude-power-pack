---
description: Risk-graded permission audit - wraps native /fewer-permission-prompts with allow/ask/deny tiers
allowed-tools: Bash(python3:*), Read(*.json), Edit(*.json), Write(*.json)
---

# Security: Permissions Audit

A risk-graded wrapper around Claude Code's native **`/fewer-permission-prompts`**.
The native skill does a binary read-only / skip split and emits an allowlist only.
This command adds `scripts/classify-tool-risk.py` to sort every observed tool call
into risk tiers, then proposes a full **allow / ask / deny** policy.

> Use the native `/fewer-permission-prompts` for the quick read-only allowlist.
> Use this when you also want the mutation and danger tiers surfaced and guarded
> (it never edits `permissions.ask` / `permissions.deny` unless you asked for the
> graded policy, which this command does by design).

## What it produces

- **allow** - read-only commands not already auto-allowed (e.g. `git fetch`) +
  the *safe, reversible* subset of local writes (`git add`, `git commit`,
  `mkdir`, `git worktree add`) + read-only MCP tools seen >= 3 times.
- **ask** - the recoverable-but-dangerous tier, gated *even under auto-accept*:
  `git push --force`, `git reset --hard`, `rm -rf`.
- **deny** - secrets that must never be auto-edited: `.env`, `*.pem`, `*.key`,
  `id_rsa*`.

## Steps

1. **Run the graded classifier** over recent transcripts:
   ```bash
   python3 scripts/classify-tool-risk.py --limit 50
   ```
   (Run from the CPP checkout. It scans `~/.claude/projects/**/*.jsonl` across all
   projects, not just the current one.)

2. **Present the tiers** as a table (tier, count, examples, verdict). Note that
   the READONLY-AUTO tier is already covered by Claude Code and needs no rule -
   do not propose those (see the native skill's auto-allow list).

3. **Propose the policy from the tiers:**
   - `allow`: READONLY-ADDABLE + the SAFE subset of WRITE-LOCAL. Exclude anything
     with a data-loss mode - `git checkout`, `git rm`, `git branch -D`,
     `git worktree remove`, `git reset` classify as DESTRUCTIVE, not allow.
     CODE-EXEC / DUAL-USE-NET / SCRIPT-EXEC are **never** allowlisted (arbitrary
     execution or ambiguous network I/O).
   - `ask`: the DESTRUCTIVE tier (force push, `reset --hard`, `rm -rf`) so it
     prompts even under auto-accept.
   - `deny`: secret files (`.env`, `**/.env`, `*.pem`, `*.key`, `id_rsa*`).

4. **Merge into the project `.claude/settings.json`** (NOT `settings.local.json`,
   NOT `~/.claude/settings.json`): preserve existing keys and entries,
   de-duplicate, never remove or reorder. Precedence is **deny > ask > allow**, so
   a secret `deny` overrides a broad `Edit(**)` allow.

5. **Report**: what was added to each tier, what was already covered by Claude
   Code's auto-allow (so no rule was needed), and what was excluded and why
   (e.g. dropped `python3`/`uv`/`make` - arbitrary code execution; dropped
   `curl`/`gh api` - dual-use network).

## File-edit scope (the git-tracked nuance)

To auto-allow file edits "only within the git commit list": Claude Code
permissions are path-glob based, not git-aware, so this cannot be expressed
directly. Two implementations:

- **Approximation (default):** `Edit(**)` / `Write(**)` for the repo tree plus a
  `deny` list for sensitive gitignored files (`.env`, keys).
- **Exact (offer):** a `PreToolUse` hook that runs `git check-ignore` on the edit
  target and blocks ignored paths. This literally scopes edits to tracked files.
  Offered, not applied by default.

## Notes

- Wraps, does not replace, the native `/fewer-permission-prompts` (a built-in
  Claude Code skill, not a CPP skill - which is why its graded extension lives
  in CPP).
- Classifier: `scripts/classify-tool-risk.py` (the **canonical** risk taxonomy).
  Re-run anytime for a fresh view.
- Complements the **real-time** side: the `#482` permission-census hook
  (`scripts/hook-permission-census.sh`) captures prompts as they happen and
  vendors the same taxonomy inline. This command is the **retroactive** side
  (mine all transcripts, propose a policy in one pass). `scripts/tool-risk-drift.py`
  guards the two taxonomies' safety-critical sets in sync.
- The destructive `ask`/`deny` guards are more protective in
  `~/.claude/settings.json` (global, every project); the allowlist is
  project-scoped by design. Offer to promote the guards to global.
