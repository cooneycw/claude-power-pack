# Flow run record - issue #1865

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=d05b7fe3d54a49c7beed965534c89dfa -->
## Run 1

- Run-id:            d05b7fe3d54a49c7beed965534c89dfa
- Run-start:         e32c06edfb52175e4a0678fe51a9a6aea56f671d
### Section A - What this issue wants
Reviews cost time, but nobody regularly counts which findings helped or why defects escaped them. Add a monthly report showing merged fixes with missing explanations and the results of committed second-model reviews. Missing data stays visible as UNKNOWN, so it cannot look like success.

### Section B - Still needed
Verdict: Still needed
Evidence: #1865 and #1850 owner rulings read; main e32c06edfb52175e4a0678fe51a9a6aea56f671d has no review-yield-report.py. Fresh isolated GitHub clone; no sibling worktrees in this clone. Orchestrator assigned this issue and approved plan in mailbox #36329, amending #36325. Tier 1 vehicle status pending owner; proceed as ordinary issue.

### Section C - Proposed changes
1. scripts/review-yield-report.py - read-only paginated GitHub collector, offline fixtures, Markdown report, canonical answer parsing, UNKNOWN denominators, latest cumulative receipt per issue in period.
2. tests/test_review_yield_report.py - missing/present negative pair, unreadable and zero populations, missing canonical markers, date boundaries, dispositions and passes, collector failures/pagination, CLI from external cwd.
3. tests/fixtures/review-yield-report/ - committed missing/present/unreadable fixture inputs.
4. .claude/commands/monthly/create.md - informational report invocation; never block creation, within word budget.
5. docs/scripts/review-yield-report.md - usage, observation bounds, fixture contract.
6. docs/scripts.md - script inventory.
7. controls/census.md - classify new report under existing reporter exclusion; fixtures still committed per issue acceptance.
8. .claude/verify-coverage.json - account for fixture-tested report.
9. Makefile - targeted report tests.
10. docs/flow-runs/issue-1865.md - approved plan and evidence.
11. docs/flow-runs/issue-1865.as-read.md - issue snapshot.
12. docs/measurements/counter-model/ - runtime-derived different-model review receipt.
Scope: approximately 12 paths plus fixtures, stdlib implementation. No JSON output or gate. No dependency on #1864.
Risks: incomplete API reads, missing provenance, duplicate cumulative receipts; report explicitly labels UNKNOWN, source coverage, and selection. No material concern found; informational reporting is proportional.
Reader search: grep found known monthly-review.py reader in monthly/create.md. New Markdown is read by monthly:create and user; integration tests consume actual CLI output. No new machine consumer.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test - main checkout and linked worktree layouts with fixture-owned temporary repositories |
| Harness | will test - Claude install / Codex install source and generated mirror; live Claude not covered |
| Driver | not applicable - flow drivers unchanged |
| Coordination | not applicable - no Kyle coupling |
| CI provider | not applicable - no CI status parsing |
| Project state | will test - a repository that has adopted a feature's file or record / one that has not; absent UNKNOWN |
| Toolchain version | not covered - installed Python only; no version matrix |
| Clone shape | not applicable - GitHub API main tree, no local history dependency |
| Run location | will test - invoked from the CPP root / from another directory |
| Gate target | not applicable - report does not run a target interpreter |
| Wave role state | not applicable - no role state changes |
| Reader: monthly:create and user | tested against real output - fixture CLI integration; source and generated Codex command inspected |

Approval: granted by orchestrator mailbox #36329 (plan #36325), 2026-11-21.
Tier 1 skip list: expanded Reader/lane narrative; spec artifacts; automatic docs-generation/C4/CLAUDE-README review step. Approval, second-model review, negative controls, finish gate and CI retained.
