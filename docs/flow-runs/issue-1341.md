# Flow run record - issue #1341

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=b86d11f11c304e4fb15cf5b1fb831cb2 -->
## Run 1

- Run-id:            b86d11f11c304e4fb15cf5b1fb831cb2
- Run-start:         75fb4497140b5a0584a19c8761a98e83ce66e612
- Issue:             #1341
- Base SHA:          75fb4497140b5a0584a19c8761a98e83ce66e612
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          run48:cpp2-orch (cpp-wave2 orchestrator), mailbox message 2439 replying to plan 2437
- Recorded at:       2026-09-28T22:10:00Z

### Section B evidence
Reframe (item 1): the issue names `.claude/cicd-state`, which never existed; the runner writes `.claude/runs/<run_id>.json` (lib/cicd/state.py:263). `git log -S'cicd-state' -- lib/cicd` returns nothing.
Commits since filing touching lib/security or tests/conftest.py: none. Earlier commits on these files, none addressing these items: 1a06a05, 75494ed, bdd2d14, 693c477, 5a4d7fc.
Merged PRs on/after filing date: #1306-#1340, none touching these files; main is still 75fb449.
Duplicate/superseding issues: none (only parent #1268).

### Section C - the approved plan
1. `lib/security/modules/secrets.py` - skip files under `.claude/runs/` relative to the scan root only.
2. `lib/security/modules/pip_audit.py` - replace the -O-erasable assert with an explicit RuntimeError.
3. `tests/conftest.py` - `_guarded_binaries` anchors on module-level `REPO_ROOT`.
4. `tests/test_secret_scan.py` - red case (RunState.save output not counted) plus two-sided control (`.claude/other.json` and nested `sub/.claude/runs` still scanned).
5. `tests/test_pip_audit.py` - red case under `python -O`: (None, None) export raises and pip-audit is never invoked.
6. `tests/test_test_binary_guards.py` - red case: pytester sub-run with copied conftest attributes a docker skip instead of UNKNOWN.
7. `docs/decisions/0010-bandit-low-band-disposition.md` - dated amendment on the pip_audit B101 row and bound.
Scope: 7 files, ~120 lines. Risks: a secret inside runner state is no longer flagged (accepted per #1268 ruling); pytester test adds a subprocess; CI runs as root (no mode-bit fixtures).
