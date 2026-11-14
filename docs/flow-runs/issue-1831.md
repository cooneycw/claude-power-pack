# Flow run record - issue #1831

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=0825157b7c3c49e7b362993a0a0e3394 -->
## Run 1

- Run-id:            0825157b7c3c49e7b362993a0a0e3394
- Run-start:         93ae85402adc58f3a3369a588547b459b62e2cc7
- Issue:             #1831
- Base SHA:          93ae8540
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (the user of this interactive session, "approved", 2026-11-14)
- Recorded at:       2026-11-14T20:40:00Z

### Section B evidence
Commits since filing (2026-11-14T19:22Z) touching the gate or its tests: 93ae8540 (#1834, introduced the lookup; defect at scripts/flow-finish-gate.sh:434). Merged PRs since filing: #1834 (the only one touching this code). Duplicate or superseding issues: none. Host scan: no unpushed commits touching the gate.

### Section C - the approved plan
1. `scripts/flow-finish-gate.sh` - look the PR up with `gh pr list --head <branch> --state open --json number,headRefName,isCrossRepository` (with `-R owner/name` when derived from origin); pass `--pr` only when exactly one same-repository PR whose head is this branch answers; keep the 15s bound and no-timeout-no-lookup
2. `tests/test_flow_finish_gate.py` - fake gh answers `pr view` and `pr list` differently; new layouts: all-digit branch (red: current gate passes --pr 123), zero matches, two matches, head-branch mismatch, cross-repository match; existing layouts keep their expectations
3. `docs/scripts/flow-finish-gate.md` - one line under the #1828 lease identity section
4. `CHANGELOG.md` - Unreleased line

Scope: 4 files, about 60-90 lines, mostly tests.
Risks: an older gh without isCrossRepository fails the lookup and --pr is omitted (fails safe). No material concern found.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test - main checkout (the test builds a plain repository); linked worktree not tested, the lookup reads only the branch name |
| Harness | will test - Claude install (the gate run directly); Codex install not covered |
| Driver | not applicable - the change is inside the gate, the same for every caller |
| Coordination | will test - with Kyle through the test's stub authority; without Kyle the lookup is never reached (existing tests) |
| CI provider | not applicable - no CI provider path touched |
| Project state | not applicable - no adopted file read |
| Toolchain version | not covered - tested against a fake gh; no live gh version matrix |
| Clone shape | not applicable - no history read |
| Run location | not applicable - unchanged |
| Gate target | not applicable - unchanged |
| Wave role state | not applicable - no wave path |

Reader: the lease's --pr field - the operator reading `kyle-lock status full-suite`; now omitted where it was wrong. Verdict line and exit codes unchanged.
