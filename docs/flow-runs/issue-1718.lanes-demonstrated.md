# Lanes demonstrated - issue #1718

This file covers the first change for the issue (the two tests that rebuilt the environment the suite runs from, and the private 30 second limit). The second change adds its own rows.

| Lane | What was demonstrated |
|---|---|
| Checkout | Linked worktree and plain clone: before the change, running the two tests replaced a Python 3.12 environment holding 61 packages with an empty Python 3.11 one, in both. After it, in both, the tests pass and the surrounding environment is still 3.12 with its packages. Main checkout: not run there. |
| CI provider | Woodpecker: not yet demonstrated when this file was written - the pipeline for this change had not run. What is to be read from its log: that the step-9 test runs rather than skips on the CI image (Python 3.11 only), and that the six dual-runtime cases skip with the reason naming Python 3.12. The skip-reason line and the root tripwire named in the plan belong to the second change. GitHub Actions: not covered. |
