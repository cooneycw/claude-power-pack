# Lanes demonstrated - issue #1727

What was actually exercised for each lane the plan answered "will test".

| Lane | What was demonstrated |
|---|---|
| Checkout | `tests/test_runner.py` in a linked worktree. The removal is pinned: `python -m lib.cicd resume x` exits 2 with argparse's invalid-choice message; `lib.cicd.runner.resume_run`, `lib.cicd.resume_run` and `DeterministicRunner.resume` are gone; `status` reads a state file written earlier. `run`'s automatic resume is unchanged: `test_resume_from_failed`, `test_resumes_and_carries_lint_when_the_tree_is_unchanged`, `test_falls_back_to_unconditional_resume_when_unverifiable`, `test_resume_state_failed_then_auto_resumed_json_uses_selected_buffer` and `test_resume_state_discarded_candidate_is_not_selected` pass untouched, and a new end-to-end test resumes a failed run on an unchanged tree. The main checkout was not separately exercised |
| Harness | `tests/test_codex_skill_sync.py` and the bundle tests in the finish gate. A live Codex run was not exercised |
| Project state | The finish gate's runner lane end to end: the full gate on this branch calls `python -m lib.cicd run` for the `finish` plan, as it did on main before the change; it never called `resume` |
