# Flow run record - issue #1713

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a78066e3993c44d1b472bc436531b77e -->
## Run 1

- Run-id:            a78066e3993c44d1b472bc436531b77e
- Run-start:         545267b95a6ff344829f9cd625c82b95e5f341ef
- Issue:             #1713
- Base SHA:          545267b95a6ff344829f9cd625c82b95e5f341ef
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1713", outbox rev 17, 2026-11-11T19:43:30-05:00
- Recorded at:       2026-11-12T00:43:52Z

### Section B evidence
- commits touching the helpers since filing: none
- PRs since filing: #1720, #1721, #1722 merged; #1729 in CI; none touches these files
- duplicate/superseding issues: none
- row 84 was already fixed by #1493 (tests/test_lane_serveability_values.py); the rollover list had it wrong

### Rulings and gate conditions (orchestrator)
- Fix here: 612, 670, 584 (report, not refuse), 634 in flow-start-resolve.sh and gate-lib.sh. One PR.
- 670 needs no coordination issue; fail-open when the url cannot be read, said in the code.
- Declined, recorded on #1713: 667, 543. Declined here with a Nit Store comment: 659.
- Barred features 575, 658, 629, 657: one Nit Store comment each, so #1713 can close.
- 563 joins #1719; the third 634 file rides with #1726; the wider line-range pattern is one Nit Store comment.
- 612: restore in a finally block, only paths compliance marked; three tests (normal run, failed diff, pre-existing intent-to-add entry).
- 670: the test asserts no branch, worktree or claim was created.
- 584: note scoped to Section C; stdout and exit code byte-identical with and without it.
- 634: bounded by the end of the header comment; help test red against the line-range version.
- #1713 carries a table of all thirteen rows before the PR closes it.
- make lint, make typecheck; two review passes; no push until the merge slot.

### Section C - the approved plan
1. `scripts/flow-plan-record.py` - compliance restores the index entries it marked (612); approve notes on stderr each numbered Section C line that yields no path (584)
2. `scripts/flow-start-resolve.sh` - refuse a pull request number (670); --help prints the whole header (634)
3. `scripts/gate-lib.sh` - --help prints the whole header (634)
4. `tests/test_flow_plan_record_index.py` - index unchanged after a normal run, after a failed diff, and a pre-existing intent-to-add entry survives; the approve note is scoped to Section C
5. `tests/test_flow_start_resolve_pr_number.py` - a pull request number is refused and nothing is created
6. `tests/test_flow_helper_help.py` - --help of both scripts prints the whole header

Scope: 6 files, about 60 lines of script change, about 200 lines of test.

Risks: the restore must not unstage an entry the user marked before compliance ran; the pull-request check depends on gh returning a url and fails open on that one field; both helpers are bundled into generated Codex mirrors.

### Lanes for this change

Added after approval, on the approver's instruction (wave orchestrator, 2026-11-11: the plan was approved without this table, which `/flow:eli5` has required since #1695 landed).

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | Index restore: the first cut tested only a main checkout; `test_the_index_is_restored_in_a_linked_worktree` now runs compliance in a linked worktree, which has its own index and is where a flow run executes it. Pull-request refusal: tested from a clone; it happens before any layout-dependent step |
| Harness | will test (Claude install); not covered (Codex install) | Claude install: the tests run the checkout's helpers, which the install symlinks. Codex install: both helpers are bundled into generated mirrors that `make codex-skills` rebuilds and checks in the gate; no test runs them from a Codex bundle |
| Driver | not covered | The delegated drivers call the same helpers; no live delegated run is exercised. No driver-facing output changed |
| Coordination | not applicable | No coordination path is touched |
| CI provider | not applicable | No provider-dependent code is touched |
| Project state | will test | A repository with no plan record: `test_the_index_is_restored_when_the_repository_has_no_plan_record`. Compliance marks files before it looks for the record, so the not-adopted answer must restore them too |
