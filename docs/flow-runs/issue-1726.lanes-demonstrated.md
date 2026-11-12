# Lanes demonstrated - issue #1726

This file covers the first change for the issue (the refusal tests for the merge and cleanup helpers, and the guard's `--help`). The second change, the three controls, adds its own rows.

| Lane | What was demonstrated |
|---|---|
| Checkout | Every case in `tests/test_merge_tail_refusals.py` builds a main checkout plus a linked worktree in a temporary directory and runs the helper from the one the case names; 60 cases. With the refusal's exit deleted from the helper, 32 of 33 mutations fail a test (the one that does not is an equivalent mutant in the sweep, recorded on the issue). Not demonstrated: the helpers run from a bare repository. |
| Harness | Claude install: `flow-worktree-guard.sh --help` is run through a symlink, as the installed copy is reached, and prints its own header (`tests/test_flow_helper_help.py`). Codex install: not covered - no test runs the helpers from a Codex bundle. |
| CI provider | Recorded output only: `gh-pr-merge.sh`'s cases feed it recorded `gh` output through the stub the existing tests use. No live provider is called by these tests. |
