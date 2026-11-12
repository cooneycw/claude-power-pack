# Lanes demonstrated - issue #1710

What was actually exercised for each lane the plan answered "will test" (rows 572, 646 and 689).

| Lane | What was demonstrated |
|---|---|
| Checkout | `tests/test_counter_model_adapters.py` and `tests/test_counter_model_review.py` in a linked worktree. 24 of the new tests failed on the unfixed writer and all pass on the fix; the two row 689 assertions failed before that change. The main checkout was not separately exercised |
| Harness | `make command-docs-budget-check` with `code_review.md` at 6,359 words before and after; `tests/test_codex_skill_sync.py` passed in the finish gate; the document edit was read old against new by an agent that did not write it. A live Codex run was not exercised |
| Driver | The writer driven end to end with fixture transcripts: a Claude implementer and a Claude reviewer whose names differ only by the context-window tag (refused as overlap, four variants); a Codex implementer with a Claude reviewer the same way; a Claude reviewer whose transcript names one model both ways (accepted as one). A real delegated run was not exercised |
| Project state | The committed receipts of this repository (375), kyle (326), skillc (153) and a fresh clone of kyle-candidate at ff51017 (284) validated under the old and the new validator: no verdict differs. One receipt mutated to a tagged self-review pair validates clean on the old validator and is refused on the new, so the comparison can show a difference |
