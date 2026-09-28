# Flow run record - issue #1299

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1299
- Base SHA:          84f414e95fb22c6ea2856da6d3c4a096530ea614
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45 orchestrator (kyle fleet mailbox msg 1774, reply to ELI5 report msg 1773)
- Recorded at:       2026-09-28T11:00:20Z

## Section B evidence
- commits since 2026-09-27T18:14Z touching lib/security or lib/cicd/manifest.py: none.
- PRs: none. dup/super: none (only #864, the nit store).
- Measured: the same planted key plus the same .claude/security.yml suppression give
  FAIL under system python3 (no PyYAML; config.py falls back to defaults silently)
  and PASS under the uv venv python. skillc has no .claude/ directory; its
  .gitleaks.toml allowlist is one exact-value regex.

## Section C - the approved plan
1. `lib/security/config.py` - an unreadable .claude/security.yml (PyYAML missing, parse error) raises ConfigUnreadable naming the file, sys.executable and the cause; never defaults. Suppression gains an optional exact-value `secret:` regex (orchestrator ruling msg 1774).
2. `lib/security/models.py` - Suppression.matches honours `secret:` against the finding's matched value.
3. `lib/security/cli.py` - every command catches ConfigUnreadable; gate prints SECURITY_GATE UNKNOWN (naming the interpreter) and exits 2. On a block with .gitleaks.toml present and no suppressions, print a hint with an id+path+secret example that never prints the secret.
4. `tests/test_security_gate_suppressions.py` - negative control through the CLI on real temp repos: key outside the suppression blocks, inside passes; same-rule different value in the same file still blocks with `secret:` (also run on pre-fix code); unreadable yaml -> UNKNOWN exit 2 (red pre-fix); hint present/absent; malformed yaml -> UNKNOWN.
5. `lib/security/README.md` - document suppressions (with `secret:`) as the answer to a planted test key, and that .gitleaks.toml is not read, and why.

Scope: ~5-7 files, ~300-450 lines. Risks: (a) behaviour change - an unreadable
security.yml now blocks where it silently defaulted; (b) id+path without `secret:`
remains coarser than a gitleaks exact-value allowlist. skillc's own
.claude/security.yml is out of scope: file a skillc issue after merge.
