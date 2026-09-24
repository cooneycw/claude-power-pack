# Flow run record - issue #1241

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1241
- Base SHA:          37bd61c
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the session owner (interactive reply "approved")
- Recorded at:       2026-09-24T18:05:00Z

## Section B evidence
- commits: 37bd61c (#1249) only; it does not touch the run_harness(ROOT) calls
- PRs: 1231, 1234, 1237, 1238, 1240, 1243-1249 merged; none change the four no-arg calls
- dup/super: #1242 (closed sibling), #970 (unrelated); none supersede
- Remedy 2 already delivered: test_an_untracked_control_file_refuses_the_green carries
  @pytest.mark.timeout(_TEST_BUDGET) with _TEST_BUDGET = 300 since beba72d (#1193)

## Section C - the approved plan
1. `tests/test_negative_controls.py` - session-scoped `real_battery` fixture running run_harness(ROOT) once, consumed by the four no-arg tests; --strict/--quiet/--verify-provenance calls stay uncached; plus an AST tripwire allowing exactly one bare run_harness(ROOT) call in the module, red-run against the pre-fix file (4 calls)
Scope: 1 file, ~40 lines
Risks: the shared result is sampled once per worker (the no-arg callers do not take the #1061 lock today, unchanged here); fixture cost lands on the first consumer's 120s budget as today; the tripwire is a new rule for future authors
