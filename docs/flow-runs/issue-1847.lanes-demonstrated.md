# Lanes demonstrated - issue #1847

<!-- lanes-demonstrated run=b58c22cac5104b62bcb58f4e25bb10ac plan=06354690770777e74d644309a5bd1ae1fa80d32f988867f8f98a47cbf6779e3d -->
| Lane | Result | Test or observation |
|---|---|---|
| Checkout | passed | main checkout: every temp-repo test in `tests/test_codex_review_run.py`; linked worktree: `test_a_linked_worktree_is_reviewed`, and all three real counter-model reviews ran in this run's linked worktree |
| Driver | passed | `/flow:auto`: this run's Step 6 ran the helper three times and wrote its receipt; delegated drivers not applicable, exempted in `docs/agents/driver-parity.json`, `make driver-parity-check` ok |
| Project state | passed | adopted: `test_enrolled_step2_uses_the_shipping_patch_producer`, `test_a_transcript_inside_the_work_tree_is_refused_before_the_review[enrolled]`; not adopted: the same test `[not-enrolled]` and every other e2e test |
| Clone shape | passed | full clone: every e2e test; shallow main-only clone: `test_a_real_shallow_clone_with_no_reachable_ancestor_is_unavailable` |
| Run location | passed | from the root: every e2e test; from another directory: `test_a_subdirectory_caller_reviews_the_whole_change`, `test_a_caller_outside_a_checkout_is_unavailable_and_runs_nothing` |
