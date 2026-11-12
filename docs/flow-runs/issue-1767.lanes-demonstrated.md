# Lanes demonstrated - issue #1767

| Lane | What was demonstrated |
|---|---|
| Checkout | Plain repository and linked worktree, by fixture: `test_the_clause_is_the_same_from_a_plain_repository_and_a_linked_worktree` builds the same project both ways (the linked one asserts its `.git` is a file) and reads the clause for each verdict word in each - two lanes missing, one missing, none missing, and an unreadable file. A second test shows the lane file read is the worktree's own, not the main checkout's. Main checkout of a real project: not run there. |
| Harness | Claude install: Step 6's text is checked against the line the helper really prints, for each verdict word, with and without the clause, and following the stderr note literally clears the clause. Codex install: the generated mirror of `flow/auto.md` is rebuilt and checked by `make codex-skills-check`; no Codex session is run. |
| CI provider | Woodpecker: not yet demonstrated when this file was written - the pipeline for this change had not run. To be read from its log: the `controls/flow-plan-record-lanes-verdict` lines in the `negative-controls` step. GitHub Actions: not covered. |
| Project state | A project with no lane file, a waived plan, and a plan with no will-test answer: stdout, stderr and exit code identical to the helper before the change, for each verdict word, with and without a file at the demonstrated path, and with the lane file made unusable (27 comparisons). |
