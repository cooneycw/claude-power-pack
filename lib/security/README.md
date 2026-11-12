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
  carries no value is never suppressed by a `secret` rule. The
  assignment-pattern findings (`HARDCODED_PASSWORD`, `HARDCODED_SECRET`) DO
  carry their value since #1405, so they can be pinned with `secret` too.
- The value you declare in `secret:` is not itself reported when it appears in
  `.claude/security.yml`. Any OTHER value in that file still is.
- Allowed keys are exactly `id`, `path`, `secret` and `reason`. Anything else is
  refused, not ignored: a misspelt `secrets:` would otherwise leave a wider
  suppression than the one written.

### Test passwords, sentinels and shell substitutions (issue #1717)

**What the scanner reports, and why it cannot tell these apart.**
`HARDCODED_PASSWORD` and `HARDCODED_SECRET` fire on a password-like name
followed by a quoted value. `password="privtest"` in a test, a sentinel such as
`LEGACY_DB_PASSWORD = "..."`, and a shell line such as
`pg_password="$(generate_secret)"` all have that shape. The first two are
literals, and a pattern cannot know whether a literal is a credential. The
third holds no secret, but whether the shell substitutes a value depends on its
quoting, escaping and nesting across the file, which a pattern over one match
cannot establish. **So the scanner reports all three, in every path, and does
not go easier on tests or on shell files.** The repository that knows a line is
harmless says so, in `.claude/security.yml`.

**Declaration 1: a path suppression by id.** For a tree of test values:

```yaml
suppressions:
  - id: HARDCODED_PASSWORD
    path: 'tests/.*'
    reason: "test fixtures and sentinels, not credentials"
```

The risk, in one sentence: it also silences a REAL password pasted anywhere
under that path, so keep the path as narrow as the list of files allows.

**Declaration 2: an exact value, pinned with `secret:`.** For a known harmless
line, such as a shell substitution:

```yaml
suppressions:
  - id: HARDCODED_PASSWORD
    path: '^docker/install\.sh$'
    secret: '\$\(generate_secret\)'
    reason: "fetched at run time; no secret is written in the file"
```

The risk, in one sentence: it clears that exact text wherever the path matches,
so a different value on the next line still reports, and a `secret:` pattern
written loosely (`.*`) is a path suppression in disguise.

`tests/test_security_scanners.py` (`TestTheConsumerDeclaresWhatIsHarmless`)
shows each declaration clearing exactly what it names.

**Tried and withdrawn: an exemption for shell substitutions in the scanner.**
Issue #1717 first built one: in a shell file, do not report a double-quoted
value that is a substitution. Two counter-model review passes found five ways
to hide a hardcoded password behind it, and it was removed before it merged:

1. an apostrophe inside the double quotes, after the reference;
2. a second, literal segment joined on after the closing quote;
3. the whole assignment wrapped in single quotes, where nothing is substituted;
4. a quoted parenthesis inside `$(...)`, which ended the substitution early and
   left a literal suffix the bracket count read past;
5. single-quote context that is not visible on one line: an escaped apostrophe,
   a single-quoted string spanning lines, a quoted here-document.

Each fix added more shell lexing to a pattern matcher, and in a detector a miss
is silent. `TestNoShellSubstitutionExemption` in
`tests/test_security_scanners.py` pins every one of those lines as reported;
read it before proposing an exemption again.

**`.gitleaks.toml` is not read by this gate.** The quick scan is CPP's native
pattern matcher, not gitleaks. Gitleaks allowlists carry regexes, paths, commits,
stopwords and per-rule scoping; a translator honouring some of those keys and
dropping the rest would suppress less than the file claims while appearing to
honour it. When the gate blocks in a repository that has a `.gitleaks.toml` and
no suppressions, it prints a hint with the example above. It never prints the
value.

### Files with no extension (issue #1737)

The secret scan selects most files by extension. Until #1737 that was the only
rule, so `bin/deploy`, a git hook, a `Makefile` or a `Dockerfile` was never
opened and the scan still reported "No secrets found in N source files". Two
rules now add files; neither changes which files the extension rule selects.

| Read | Rule |
|---|---|
| A file with no suffix whose first two bytes are `#!` | The shebang decides, whatever the interpreter |
| `Makefile`, `GNUmakefile`, `makefile`, `Dockerfile`, `Containerfile`, `Dockerfile.<x>` | Exact basename; `Makefile.bak`, `my-Dockerfile` and a bare `Dockerfile.` are not on the list |

Stated answers:

- **A shebang and no execute bit: read.** Mode bits are lost on some checkouts.
- **An execute bit and no shebang: not read.** It is far more often a binary
  than a script, and it is counted in the line below.
- **Not read, for this population only:** a file with a NUL byte in its first
  8 KB (binary), a file over 1 MB, a symlink, and anything that is not a
  regular file. A symlink is never followed, inside the scan root or out of
  it; its target is read under its own name if it qualifies. A FIFO or device
  is refused without being opened for reading, so the scan cannot wait on one.
- **A file that does not qualify costs at most its first 8 KB**, and a
  qualifying one is read to at most 1 MB.

**Assumption.** The scan reads a tree that is not being modified while it
runs. It is not hardened against a concurrent writer - a file or directory
swapped between being listed and being read - for these files or for the ones
selected by extension. The guards above protect it from an odd file, not from
a race.

Whenever an extensionless file is left unread, the scan says how many and why,
on its own line:

```text
NOT READ: 3 file(s) with no recognised extension were NOT read (2 no shebang or known name, 1 binary)
```

In `--json` that is the `unexamined` list. It is deliberately not a `SKIP`
line: the number of `SKIP` lines is printed as `skipped-checks=` on the
`SECURITY_GATE` line, where it means checks that could not run. On that line
only `secrets-scanned=` rises.

**Finding counts can go up on upgrade.** A Makefile is full of
`PASSWORD=$(VAR)` shapes, which are reported like any other assignment (see
the section above). Declare the harmless ones with a path suppression for the
file; a suppression for a file not yet scanned is inert, so it can be added
before the upgrade.

Cost: the extra pass reads at most 8 KB of each extensionless file git does
not ignore. Measured on a 60,000-path tree, the scan went from about 3.6
seconds to about 6.8.

Still not read: a file with an extension outside the scanner's list (`.txt`,
`.md`, `.sql`, `.env`-unlike config names), and anything gitignored.

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
