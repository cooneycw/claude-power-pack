# Lanes demonstrated - issue #1700

What was actually exercised for each lane the plan answered "will test".

| Lane | What was demonstrated |
|---|---|
| Checkout | `tests/test_counter_model_review.py` in a linked worktree: an escalated write records the true count and the ruler; five passes with no ruling refuses; each malformed ruling is refused by the writer and by the validator; a skipped receipt cannot carry an escalation; nine passes with a raised cap of nine is accepted and eleven is refused. The main checkout was not separately exercised |
| Harness | `make command-docs-budget-check` with `auto.md` at 10,410 words before and after; the Step 6 wording read old against new by an agent that did not write it; `tests/test_codex_skill_sync.py` in the finish gate. A live Codex run was not exercised |
| CI provider | The gate's `--enrolment-only` mode on this repository's receipts with the gate script unchanged (`git diff origin/main -- scripts/flow-finish-gate.sh` is empty). The pull request's own pipeline is the live run |
| Project state | Main's gate script against scratch repositories holding one receipt each: five passes with a ruling prints `receipt:` and passes; five passes with no ruling also prints `receipt:` and passes; three passes prints `receipt:` and passes. The validator accepts the first and third and refuses the second. Committed receipts re-validated under main's validator and this one: this repository 383, kyle 326, skillc 153, kyle-candidate 284 (clone at ff51017): no receipt flips between valid and invalid; six kyle receipts (and the same six in kyle-candidate) that record 4 to 9 passes with no ruling are refused by both, with a reworded message |
