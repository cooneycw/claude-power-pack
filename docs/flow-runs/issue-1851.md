# Flow run record - issue #1851

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=385e634fa8ad451bb4264aa148ab4c39 -->
## Run 1

- Run-id:            385e634fa8ad451bb4264aa148ab4c39
- Run-start:         2df9b1c6846ce52d99058d9b085f0d70e0ab93cb
- Issue:             #1851
- Base SHA:          2df9b1c6
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session reply "approved"
- Recorded at:       2026-11-16T02:20:57Z

### Section B evidence
Commits since filing touching the parity paths: 2df9b1c6 (#1856), 716b7c3f (#1855, a pure 9-line citation re-pin), 62e928b9 (#1854); none changes citation resolution. Merged PRs inspected: #1856, #1855, #1854, #1852, #1845, #1843, #1841, #1840. Duplicate/superseding issues considered: #1810 (closed), #1811 (open, different scope); none supersede. All 18 live and 18 fixture citation texts verified unique per file.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | not applicable - static read of files under --root; no git calls |
| Harness | not applicable - the Codex mirror is not cited by the policy; no command document changes |
| Driver | will test - citations bind delegated driver docs to /flow:auto steps; the control cases edit the codex driver doc and the policy, and the live table is re-checked by make driver-parity-check |
| Coordination | not applicable - no Kyle path |
| CI provider | will test - Woodpecker driver-parity-check and negative-controls on the PR; GitHub Actions is not this repo's CI |
| Project state | not applicable - CPP-internal gate |
| Toolchain version | not applicable - stdlib only, no new dependency |
| Clone shape | not applicable - no git calls |
| Run location | not applicable - unchanged; the checker resolves files from --root |
| Gate target | not applicable - CPP itself only |
| Wave role state | not applicable - no wave state |
| Reader: make verify / driver-parity-check | will test - verdict line and exit codes unchanged; live tree stays ok |
| Reader: check-negative-controls.py | will test - --control controls/driver-parity: new BAD read BAD, GOOD read GOOD, anchor blind as before |

### Section C - the approved plan
1. `scripts/check-driver-parity.py` - resolve each citation by unique text in the file; line is an optional hint used only in failure messages; distinct stale (not found) and ambiguous (multiple lines) failures
2. `controls/driver-parity/run-case.py` - add citation-text-removed, citation-ambiguous and citation-line-shift fixture modes
3. `controls/driver-parity/control.json` - register bad-citation-text-removed, bad-citation-ambiguous (BAD) and good-citation-line-shift (GOOD)
4. `controls/driver-parity/cases/bad-citation-text-removed/case.json` - new case input
5. `controls/driver-parity/cases/bad-citation-ambiguous/case.json` - new case input
6. `controls/driver-parity/cases/good-citation-line-shift/case.json` - new case input
7. `controls/driver-parity/README.md` - update case counts and state text-based citation resolution
8. `tests/test_driver_parity.py` - unit tests for removed, ambiguous, line-shift and line-omitted citations

Scope: Tier 1, about 120 lines. Risks: a short citation text matching several lines (caught as ambiguous, fails loud); line hints drift (harmless, message-only). Pre-fix red run of the line-shift case is performed, not committed.
