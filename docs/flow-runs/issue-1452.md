# Flow run record - issue #1452

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=bb46557005bf470ea11851edebd8e1dc -->
## Run 1

- Run-id:            bb46557005bf470ea11851edebd8e1dc
- Run-start:         fc87b5b80ebb650f2867b58eb5d5d8e6c55691ca
- Issue:             #1452
- Base SHA:          fc87b5b80ebb650f2867b58eb5d5d8e6c55691ca
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6510, replying to plan 6509), on the operator's instruction to complete #1452-#1454
- Recorded at:       2026-10-17T00:40:00Z

### Section B evidence
Commits since filing: fc87b5b, 268dbd2, 049483b (only 268dbd2 touches .woodpecker.yml; none touches enrolment).
Merged PRs since filing: #1451, #1455, #1456, #1457 (none adds a merge-time check).
Duplicate/superseding: #1269 (closed) already ruled #1162/#1165/#1166 a permanent gap, with no backfill (comment 5867853082); #1171 added local finish-gate enrolment.
Measured: 7 of the last 40 merged PRs carry no receipt (#1424, #1426, #1428, #1436, #1451, #1455, #1456).
Sibling worktrees: none with unpushed commits touching these paths.

### Section C - the approved plan
1. `scripts/flow-finish-gate.sh` - add `--enrolment-only [--branch NAME]`, reusing cm_enrolment_evaluate; exit 0 receipt/skipped/not-enrolled, 1 missing/unresolvable/unknown, 2 undecidable (never a pass).
2. `.woodpecker.yml` - `counter-model-enrolment` step on pull_request only: deepen the depth=1 clone, then evaluate with --branch "$CI_COMMIT_SOURCE_BRANCH".
3. `controls/counter-model-enrolment/control.json` - cases for the new mode (BAD no receipt, GOOD receipt, shallow not a pass).
4. `tests/test_flow_finish_gate.py` - mode tests and CI-step pins.
5. `tests/test_ci_config.py` - CI-shape pins that enumerate steps, if any need the new step.
6. `docs/scripts.md` - flow-finish-gate entry records the CI consumer and the one-command skip-receipt path.
7. `docs/decisions/0008-instrument-negative-control-bound.md` - census row for flow-finish-gate names the CI consumer.
8. `.claude/commands/flow/auto.md` - one line saying CI now enforces the receipt.
Scope: ~6-8 files, ~150-250 lines. Known gaps (3 historical + 7 measured PRs) are listed in the PR and on the issue; no receipts are fabricated.
Risks: every future PR must commit a receipt or a skip receipt; a GitHub fetch flake reds the step; this PR carries its own receipt.
