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
`shutil.which(...)`. The native checks always run, so the module has no hard
external dependency - but an external audit that APPLIES and could not run (the
binary absent, a crash, an unparseable report) is reported as an `UNKNOWN`
error line, never a skip or a pass (issues #1044, #1264). A skip is reserved for
an audit that does not apply: no Python manifest for `pip-audit`, no
`package.json` or `package-lock.json` for `npm audit`. The error line does not
change the gate's exit code; it makes "not checked" readable as such.

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

### A planted test key blocks the finish gate (issue #1299)

A repository that keeps fake keys as negative controls for its own leak
detector will be blocked by this gate on every finish run. **Suppress exactly
the planted value**, not the file:

```yaml
suppressions:
  - id: AWS_ACCESS_KEY
    path: '^tests/test_leak\.py$'
    secret: '<the exact planted value>'   # re.fullmatch against the FULL value
    reason: "planted negative-control fixture"
```

- `path` is a regex (`re.match`, anchored at the start) against the path
  relative to the repository root. `secret` is a regex matched with
  `re.fullmatch` against the finding's full, unmasked value. Use single-quoted
  YAML so backslashes stay literal.
- **Prefer `secret`.** An `id` + `path` suppression covers EVERY finding of that
  id in the file, so a real key committed beside the canary passes silently.
  With `secret`, a different value in the same file still blocks. A finding that
  carries no value (the assignment-pattern findings) is never suppressed by a
  `secret` rule.
- The value you declare in `secret:` is not itself reported when it appears in
  `.claude/security.yml`. Any OTHER value in that file still is.
- Allowed keys are exactly `id`, `path`, `secret` and `reason`. Anything else is
  refused, not ignored: a misspelt `secrets:` would otherwise leave a wider
  suppression than the one written.

**`.gitleaks.toml` is not read by this gate.** The quick scan is CPP's native
pattern matcher, not gitleaks. Gitleaks allowlists carry regexes, paths, commits,
stopwords and per-rule scoping; a translator honouring some of those keys and
dropping the rest would suppress less than the file claims while appearing to
honour it. When the gate blocks in a repository that has a `.gitleaks.toml` and
no suppressions, it prints a hint with the example above. It never prints the
value.

### An unreadable `.claude/security.yml` is UNKNOWN, never defaults

If the file exists but cannot be applied - PyYAML is not importable by the
interpreter running the gate, the YAML does not parse, or an entry has the wrong
shape - every command refuses:

```
SECURITY_GATE: flow_finish UNKNOWN (config unreadable: <file>: PyYAML is not importable by /usr/bin/python3; its suppressions and gate policy were NOT applied, so no verdict is given)
```

It exits `2`, distinct from a blocking FAIL's `1`. Until issue #1299 the file was
dropped silently and defaults applied. That removed the repository's
suppressions, a false block, and its stricter policy, a false pass, and both
read exactly like a real verdict. The finish step runs `python3 -m lib.security`
under whatever `python3` is first on PATH, so this is decided by that
interpreter: inside the runner's `uv run` environment it is the venv's, which
has PyYAML.

See `/security:explain <ID>` for details on any finding type, and
`.claude/commands/security/help.md` for the command-surface overview.
