# Flow run record - issue #1288

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1288
- Base SHA:          879df15
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the session's user (cooneycw), interactive "approved"
- Recorded at:       2026-09-27T14:20:00Z

## Section B evidence
- commits: none since 2026-09-27T13:33:50Z (base 879df15 is the SHA the issue cites)
- PRs: #1284, #1286, #1287 merged today; none touch the secret-scan paths
- dup/super: none; #1271 related (test isolation) but separate

## Section C - the approved plan
1. `tests/test_secret_scan.py` - `_scan` passes `--redact` and returns a safe result object; replace the four `stdout[:2000]` messages with a safe rule/file/line summary; add synthetic-token detection/redaction tests (helper and gate script) and a pytester failure-report test
2. `scripts/secret-scan-check.sh` - add `--redact` to the gitleaks call
3. `Makefile` - `secret-scan` target: add `--redact` to both branches
4. `.woodpecker.yml` - CI `secret-scan` step: add `--redact`
5. `docs/flow-runs/issue-1288.md` - this record

Scope: ~4 source files, ~120 lines. Risks: pytester import path; red case shown
against the pre-fix helper with synthetic data only; #1271 may still fail a full
workstation `make verify`.
