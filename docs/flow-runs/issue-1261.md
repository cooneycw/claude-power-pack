# Flow run record - issue #1261

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1261
- Base SHA:          75494ed900ae904520b7bf9ef285364372b89de5
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the session user (replied "approved" to the Step 3 report)
- Recorded at:       2026-09-27T00:00:00Z

## Section B evidence
- a6787d2 (PR #1286, Closes #1285): caller-supplied CODEX_AUTO_SANDBOX for /codex:auto only; /codex:code_review still hardcodes --sandbox read-only.
- 2ae3c47 (PR #1279): touches gates, none of these four items.
- Merged PRs since filing inspected: #1295, #1293, #1287, #1286, #1284, #1283, #1280, #1279, #1275, #1274, #1270, #1255 - only #1286 relevant.
- Duplicate/superseding issues: #1285 (closed, partial delivery of item 1); #1189 unrelated. None supersede items 2-4.

## Section C - the approved plan
1. `.claude/commands/codex/code_review.md` - caller-supplied CODEX_REVIEW_SANDBOX (read-only default | danger-full-access, else refused); `codex sandbox` probe emitting CODEX_REVIEW_SCOPE full|diff-only|unverified, reflected in prompt and relay; ls-files enumeration via checked temp file, exit 3 on failure
2. `templates/delegated-driver-core.md` - Step 1 via flow-start-resolve.sh + --verify; Step 3 orchestrated-run mailbox route; Step 7 backstop against explicit origin/<default> base, rev-list failure is a STOP
3. `.claude/commands/codex/auto.md` - re-rendered regions; Step 4 records pre-exec HEAD in the git dir; overrun check uses it and STOPs when missing
4. `.claude/commands/qwen/auto.md` - same as 3
5. `.claude/commands/gemma/auto.md` - same as 3
6. `tests/test_code_review_diff_range.py` - ls-files failure red/green via a git shim
7. `tests/test_code_review_sandbox_scope.py` - stub codex probe red/green; bad value refused
8. `tests/test_delegated_overrun_base.py` - own-name-upstream fixture; old @{u} form blind (red), new blocks detect + reset (green); missing base STOPs; resolver + mailbox route present

Scope: ~8 files + generated codex/skills mirrors, ~350-450 lines.
Risks: item 2 changes worktree upstream for three lanes and must ship with the overrun switch; codex sandbox probe on macOS reports unverified; item 4 is prose without a mechanical negative control.
