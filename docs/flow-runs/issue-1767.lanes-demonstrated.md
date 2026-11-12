# Lanes demonstrated - issue #1767

| Lane | What was demonstrated |
|---|---|
| Checkout | Plain repository: every test in `tests/test_flow_plan_record_lanes.py` and `tests/test_flow_auto_plan_gate.py` builds one and runs the helper in it. Linked worktree: NOT by a fixture, as the plan said it would be. What was shown instead is the helper run against this run's own record from the linked worktree the change was made in - the line below this table's file is the one it printed there. A fixture in a linked worktree is owed. |
| Harness | Claude install: Step 6's text is checked against the line the helper really prints, for each verdict word, with and without the clause, and following the stderr note literally clears the clause. Codex install: the generated mirror of `flow/auto.md` is rebuilt and checked by `make codex-skills-check`; no Codex session is run. |
| CI provider | Woodpecker: not yet demonstrated when this file was written - the pipeline for this change had not run. To be read from its log: the `controls/flow-plan-record-lanes-verdict` lines in the `negative-controls` step. GitHub Actions: not covered. |
| Project state | A project with no lane file, a waived plan, and a plan with no will-test answer: stdout, stderr and exit code identical to the helper before the change, for each verdict word, with and without a file at the demonstrated path, and with the lane file made unusable (27 comparisons). |
