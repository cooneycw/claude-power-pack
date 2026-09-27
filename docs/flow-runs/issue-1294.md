# Flow run record - issue #1294

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1294
- Base SHA:          75494ed
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          session user (cooneycw), interactive "approved"
- Recorded at:       2026-09-27T15:10:00Z

## Section B evidence
- commits: none touching lib/cicd/ or tests/test_cicd_outcomes.py since issue creation
- PRs: #1295, #1293, #1287, #1286, #1284 merged today; none touch is_test_step
- dup/super: #704 (CLOSED, fixture-only fix, pinned path-matching by design); #1271 (OPEN, origin); none supersede
- Live repro at 75494ed: finish-plan typecheck step classified as a test step in this worktree.

## Section C - the approved plan
1. `lib/cicd/steps.py` - strip directory components (any non-space run ending in `/`) from the command before `_TEST_STEP_HINT`; keep basenames; rewrite the "PATHS INCLUDED" comment to record the #1294 reversal.
2. `tests/test_cicd_outcomes.py` - invert `test_path_in_command_matches_by_design` into a regression test (checkout-path, #704 shapes, tests/-dir script NOT test; .venv/bin/pytest, run-tests.sh, pytest tests/ STILL test; real finish-plan typecheck step NOT test); confirm red on old code.
3. `tests/test_test_workers_cap.py` - update the `_relative_interpreter` docstring; fixture unchanged.

Scope: 3 files, ~60 lines. Risks: deliberate reversal of #621/#704 trade-off (directory-only test signals no longer match); final path component still scanned.
