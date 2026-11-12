# Lanes demonstrated - issue #1711

What was actually exercised for each lane the plan answered "will test".

| Lane | What was demonstrated |
|---|---|
| Checkout | `tests/test_flow_ci_status.py` run in a linked worktree; each new behaviour test was also run against the script at 5d7a9d59 and failed there, and its must-not-flip partner passed on both. The main checkout was not separately exercised |
| Harness | `make command-docs-budget-check` with `auto.md` at 10,410 and `merge.md` at 4,082 words before and after; `tests/test_codex_skill_sync.py` passed; the two document edits were read old against new by an agent that did not write them. A live Codex run was not exercised |
| CI provider | The Woodpecker lane through a stubbed `curl`: a two-line step error (one failed step), two polls with an unreadable pipeline detail then success (no stale stall line). The branch-protection read through a stubbed `gh`: stderr on a successful read, and eight combinations of a failed classic read asked twice, with and without a usable `TMPDIR`. `controls/flow-ci-status` verified with `check-negative-controls.py --control`: the new case reads UNSIGNALLED on the script at 5d7a9d59 and detected on this one. Not exercised: a live pipeline, and the Actions lane beyond its existing tests |
