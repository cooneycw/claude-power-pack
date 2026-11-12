# Lanes demonstrated - issue #1760

What was actually exercised for each lane the plan answered "will test".

| Lane | What was demonstrated |
|---|---|
| Checkout | The documents' own bash blocks, extracted and run from scratch projects in a linked worktree: `tests/test_flow_deploy_target.py` (24 tests; 9 fail against the deploy document at 4f34005f) and `tests/test_flow_finish_security_fallback.py` (9 tests; 8 fail against the finish and help documents at 4f34005f). Cases: no checkout at any location (stop, naming the three); a checkout at `~/.claude-power-pack` (the scan runs from there); a failing scan; exit 0 with no PASS line; exit 0 with a FAIL line; UNKNOWN; exit 2 with no line; a passing scan (proceeds). `/opt/claude-power-pack` was not exercised: it needs a path outside the test's HOME |
| Harness | `make command-docs-budget-check` with `deploy.md` at 1,560 of 1,561 words, `finish.md` at 4,744 of 4,744 and `help.md` at 983 of 984; `tests/test_codex_skill_sync.py`; both trimmed documents read old against new by an agent that did not write them. A live Claude or Codex run of `/flow:deploy` or `/flow:finish` was not exercised, and "the agent stops when the block exits non-zero" is not covered by any test |
| Project state | A non-default deploy target and a default target, each with a stubbed `make` and a stubbed `uv`: nothing is deployed and nothing is logged unless the scan exits 0 with its PASS line. The real scanner and a real deployment were not run |
