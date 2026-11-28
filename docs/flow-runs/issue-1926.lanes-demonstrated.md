# Demonstrated lanes for issue #1926

<!-- lanes-demonstrated run=5cd88489f9844c7e9c3239fe585c3062 plan=7c35543ff3258f9b9487eb8aaafa4fbd3ae4eac81370e1cebe0e998ee5fe8318 -->

| Lane | Result | Test or observation |
|---|---|---|
| Checkout | passed | `test_claude_install_in_main_and_worktree[False]` and `[True]` run the real helper in fixture main checkout / linked worktree layouts. |
| Harness | passed | Real Claude install helper and Codex install bundle script consume both old provenance and expanded title fixtures in `test_claude_install_in_main_and_worktree` and `test_generated_codex_bundle_uses_real_script_and_canonical_contract`. A live Claude runtime is not covered. |
| Project state | passed | `test_committed_negative_control_flags_missing_but_not_present`, `test_unreadable_is_unknown_and_not_zero_escapes`, `test_missing_receipt_directory_is_unknown` and the title population cases exercise adopted / missing / malformed sources. |
| Toolchain version | passed | Host installed Python/uv exercised by `make lint review-yield-test`, 70 passed. CI's pinned uv/Python is deferred to the PR pipeline; no local version matrix or CI-green claim. |
| Run location | passed | `test_cli_from_other_directory_reads_real_fixture_output`, source imports from the CPP root, and both generated/installed fixture readers exercise root / external callers. |

The four new title paths also failed on the exact predecessor (four failed,
three unchanged cases passed). The focused green and source hashes are recorded
in [the measurement](../measurements/review-yield/issue-1926-title-populations.md).
These are focused lane observations; the complete finish gate and PR CI are
reported separately.
