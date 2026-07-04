# `lib/security` - deterministic security orchestration

This module is the **deterministic half** of Claude Power Pack's security
surface. It backs the `/security:quick`, `/security:scan`, `/security:deep`,
and `/security:explain` commands and the CRITICAL-blocks gate used by
`/flow:finish` and `/flow:deploy`.

## The split: semantic vs. deterministic

Claude Code ships a native **`/security-review`** command (and an official
GitHub Action) that performs **semantic** code-vulnerability review - reasoning
about SQL injection, XSS, broken authorization, and insecure credential
handling by reading the code. CPP **defers to it** for that class of review and
does not duplicate it.

`lib/security` owns the **deterministic** complement that native review does not
provide:

| Concern | Owner |
|---------|-------|
| SQLi / XSS / authz / insecure-handling (semantic code logic) | native `/security-review` |
| Secret scanning (patterns + gitleaks) | `lib/security` |
| Git-history secret scanning | `lib/security` (`/security:deep`) |
| Dependency CVE audits (`pip-audit`, `npm audit`) | `lib/security` |
| `.gitignore` / file-permission / `.env`-tracked / debug-flag checks | `lib/security` |
| The blocking gate for `/flow:finish` and `/flow:deploy` | `lib/security` |

The two halves are complementary - run `/security-review` for code-logic flaws
and `lib/security` (`/security:*`) for secrets, dependencies, and the flow gate.

## Entry points

```bash
# All commands honor --path <dir> (default: current project) and --json.
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security quick
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security scan
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security deep
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security explain HARDCODED_PASSWORD
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security gate flow_finish
```

## Scan modes

| Mode | Scanners | Speed |
|------|----------|-------|
| `quick` | native only: secrets, `.gitignore`, permissions, `.env`-tracked, debug flags | ~1 s |
| `scan` | `quick` + **gitleaks** (working tree) + **pip-audit** + **npm audit** (auto-detected) | ~5 s |
| `deep` | `scan` + **gitleaks `--include_history`** (secrets committed then removed) | ~30 s |

External tools (`gitleaks`, `pip-audit`, `npm audit`) are auto-detected via
`shutil.which(...)` and skipped cleanly when absent - the native checks always
run, so the module has no hard external dependency.

## Modules (`lib/security/modules/`)

| Module | Kind | Detects |
|--------|------|---------|
| `secrets.py` | native | AWS / OpenAI / Anthropic / GitHub / GitLab / Google / Slack keys; hardcoded passwords & secrets |
| `gitignore.py` | native | sensitive patterns (`.env`, `*.key`, `*.pem`, `secrets/`) missing from `.gitignore` |
| `permissions.py` | native | world-readable secret/key files |
| `env_files.py` | native | `.env` files tracked by git |
| `debug_flags.py` | native | debug mode enabled in production config |
| `gitleaks.py` | external | secrets in working tree (and git history with `include_history=True`) |
| `pip_audit.py` | external | Python dependency CVEs |
| `npm_audit.py` | external | Node dependency CVEs |

`secrets.py` honors `.gitignore` inside a git work tree (via a batched
`git check-ignore`), so gitignored, never-committed local files (e.g.
`.claude/settings.local.json`) are not scanned - the gate flags only
*committable* risk. It fails open: outside a git repo, or on any git error, the
full tree is scanned as before. Tracked files are always scanned even if they
match an ignore pattern (`check-ignore` is index-aware).

## The gate

`python -m lib.security gate <gate_name>` runs the **quick native** scan, then
`orchestrator.check_gate` compares findings against the named gate's policy and
returns `(passed, messages)`. `/flow:finish` and `/flow:deploy` invoke this via
`lib/cicd` StepDefs; a blocked gate stops the flow (no PR / no deploy).

Default policies (`config.py`) - configurable in `.claude/security.yml`:

| Gate | Blocks on | Warns on |
|------|-----------|----------|
| `flow_finish` | CRITICAL | HIGH |
| `flow_deploy` | CRITICAL, HIGH | MEDIUM |

Severities not listed pass silently. To tune gates or suppress a known false
positive, create `.claude/security.yml`:

```yaml
gates:
  flow_finish:
    block_on: [critical]
    warn_on: [high]
  flow_deploy:
    block_on: [critical, high]
    warn_on: [medium]

suppressions:
  - id: HARDCODED_SECRET
    path: tests/fixtures/.*
    reason: "Test fixtures with fake credentials"
```

See `/security:explain <ID>` for details on any finding type, and
`.claude/commands/security/help.md` for the command-surface overview.
