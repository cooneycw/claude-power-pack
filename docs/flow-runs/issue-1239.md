# Flow run record - issue #1239

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1239
- Base SHA:          693c4773c885ac9d3224e8f74d70f45d71f15fab
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), in-session: "approved."
- Recorded at:       2026-09-24T17:13:30Z

## Section B evidence
- Commits since 2026-09-24T10:13:10Z touching scripts/check-negative-controls.py or tests/test_negative_controls.py: none
- Merged PRs since the issue date (#1231, #1234, #1237, #1238, #1240, #1243-#1248): none touch this checker
- Duplicate/superseding issues: none (#1126 closed, unrelated; #864 is the nit store)

## Section C - the approved plan
1. `scripts/check-negative-controls.py` - _tracking(): exclude derived bytecode (any path under a __pycache__/ component, or *.pyc/*.pyo) from on_disk; nothing else excluded
2. `tests/test_negative_controls.py` - two real-git tmp_path cases: tracked case + ignored __pycache__/*.pyc reports tracked (red on pre-fix code); ignored load-bearing case.json still reports UNTRACKED

Scope: small (~10 lines of logic + 2 tests). codex/skills mirrors only if the resync helper reports drift.
Risks: a name-based exclusion would hide a deliberately committed .pyc control file - accepted, bytecode is never a load-bearing control input; the second test guards against the exclusion widening.
