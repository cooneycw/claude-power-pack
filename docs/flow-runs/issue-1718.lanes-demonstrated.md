# Lanes demonstrated - issue #1718

This file covers the first change for the issue (the two tests that rebuilt the environment the suite runs from, and the private 30 second limit). The second change adds its own rows.

| Lane | What was demonstrated |
|---|---|
| Checkout | Linked worktree and plain clone: before the change, running the two tests replaced a Python 3.12 environment holding 61 packages with an empty Python 3.11 one, in both. After it, in both, the tests pass and the surrounding environment is still 3.12 with its packages. Main checkout: not run there. |
| CI provider | Woodpecker, first change, read from PR #1764's pipeline 3768 (11194 passed, 112 skipped): the owned-copy and step-9 tests RAN on the CI image (no skip names uv or Python 3.11; the missing-binary summary lists only curl and ps); the six dual-runtime cases skipped with `requires a Python 3.12 interpreter; discovery forbids downloads`; the real-history test skipped with `partial clone: real-history comparison is done by the negative-controls CI step on pull requests`. GitHub Actions: not covered. |

## Second change (run 2): curl stand-ins read the header they are piped

| Lane | What was demonstrated |
|---|---|
| Coordination | The coordination-signal test (`tests/test_gh_pr_merge.py::test_coordination_signal_preserves_queue_unless_explicitly_enabled`) run with the one Authorization write made larger than a pipe can hold: on the stub as it was, 5 failed and 1 passed (the case that expects zero polls); with the stub reading, 6 passed. The natural race did not show: 150 runs before the change and 150 after, 0 failures each, at a load average of 24 to 25 - so those loops discriminate nothing and the injected case is the evidence. No live coordination service is called. |
| CI provider | Recorded output only: the four `flow-ci-status` controls drive the gate through a curl stub standing in for the Woodpecker API. Each passes by name with `--verify-provenance` after the change, and each still passes when the header cannot be buffered; on the runners as they were, the stalled control's known-bad case read `running`. No live provider is called. |
