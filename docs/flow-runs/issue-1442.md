# Flow run record - issue #1442

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=3e11f9050ddd4397bb0fcce2290ace09 -->
## Run 1

- Run-id:            3e11f9050ddd4397bb0fcce2290ace09
- Run-start:         50261ddd1b76a042dd0bf868a869e04b67e5b27f
- Issue:             #1442
- Base SHA:          50261ddd
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), chose option A in this session: "Fix it first in a separate small PR... one entry to .claude/security.yml covering exactly that planted value in exactly that file, with a test showing a real key elsewhere is still blocked"
- Recorded at:       2026-10-12T15:20:00Z

### Section B evidence
commits: 5fd4ebe4 (#1423) added the planted fixture; none since touching .claude/security.yml (file absent on main). PRs: #1423. dup/super: none (searched "bad-critical-secret", nit store #864).

### Section C - the approved plan
1. `.claude/security.yml` - new; one AWS_ACCESS_KEY suppression, path anchored to controls/lib-security-gate/cases/bad-critical-secret/leaked.py, secret = the exact planted value
2. `tests/test_security_gate_suppressions.py` - test the REPOSITORY's own config: planted fixture passes; a different AKIA value in the same file blocks; the planted value at another path blocks; the real repo root passes

Scope: 2 files, ~60 lines.
Risks: an over-broad suppression would hide a real key - pinned by the exact-value + other-path cases.
