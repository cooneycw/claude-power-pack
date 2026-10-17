# Flow run record - issue #1472

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=9e8c402123294dc3a648ab53a46eeb82 -->
## Run 1

- Run-id:            9e8c402123294dc3a648ab53a46eeb82
- Run-start:         020349564f87d1bd2b86800f9c8e2814fd239b79
- Issue:             #1472
- Base SHA:          020349564f87d1bd2b86800f9c8e2814fd239b79
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), "yes" in the interactive flow:auto session
- Recorded at:       2026-10-17T00:00:00Z

### Section B evidence
Reproduced on 02034956 with planted CODEX_THREAD_ID: 5 failed, 2 passed (the
five issue-listed parameterizations); neither / Claude-only: 7 passed. No commits
on origin/main since filing (none touching tests/test_counter_model_review.py or
scripts/counter-model-receipt.py). Merged PRs #1463-#1471 all predate filing;
#1467 introduced the CODEX_THREAD_ID path. Duplicates: none (#864 is the nit
store origin of this finding).

### Section C - the approved plan
1. `tests/test_counter_model_review.py` - autouse fixture clearing CLAUDE_CODE_SESSION_ID and CODEX_THREAD_ID for every test; plus a nested-pytest test running the affected selection with both identities planted ambient and asserting all pass.

Scope: 1 file, ~30-40 lines. Risk: nested pytest inherits addopts/timeout (run without xdist/cache); autouse removes ambient identity for every module test (planted-env run showed no other dependence).
