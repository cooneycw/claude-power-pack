# Flow run record - issue #1728

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=6bd34a446935429eae493ef142432b74 -->
## Run 1

- Run-id:            6bd34a446935429eae493ef142432b74
- Run-start:         68d5fedf152b4446d35bd42f50e0b6c326ce43cb
- Issue:             #1728
- Base SHA:          68d5fedf152b4446d35bd42f50e0b6c326ce43cb
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, authority model orchestrator-only), by mailbox rev 39 to role cpp-1508 at 2026-11-11T23:24:10-05:00: "GATE: GO-WITH-CONDITIONS #1728" (assignment a1700hold-583-1710b-1728-g5, item 2)
- Recorded at:       2026-11-12T04:30:00Z

### Section B evidence
- `parse_fallback_failed_ids` at 68d5fedf takes the id as awk's `$2`. Commits on `scripts/flow-finish-gate.sh` since the issue was filed (3eaf643d, 46ee0dcf, 786f149c) leave it alone.
- Reproduced on 2026-11-11 at 545267b9: three failures in, two ids out, one truncated; the Python parser returns three.
- kyle, skillc and kyle-candidate have no reader of `RERUN_PASSED` outside pinned copies of this script.

### Section C - the approved plan
Conditions attached to the approval: parity is exact on the shared fixture and the test names the input shapes the fixture does not cover; if awk cannot be made equal without growing past what a reader can check, stop and report; the cap test runs through the real fallback lane with 26 distinct failures the old parser merges below 26, red on 68d5fedf; the parity test runs under the validate container's awk in CI and the report says which awk; the WARNING's count of re-run ids is corrected in both lanes through a count variable with no format change, one test per lane; the separator stays and goes to the Nit Store; two review passes, ask before a third; no push without the merge slot.

1. `scripts/flow-finish-gate.sh` - `parse_fallback_failed_ids` reads the id up to the reason separator and prints one id per line; the cap counts lines; both lanes count re-run ids by id, not by word.
2. `tests/fixtures/pytest-failed-summary.txt` - the shared input for both parsers.
3. `tests/test_flow_finish_gate.py` - parity test, cap test through the fallback lane, one count test per lane.

Scope: about 30 lines of shell, 100 of test, one fixture.

Risks: awk and the Python regex disagreeing on a shape the fixture lacks; awk dialects (the function must stay POSIX awk).

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: pytest in this linked worktree, red on 68d5fedf first |
| Harness | will test: Codex mirrors rebuilt and tests/test_codex_skill_sync.py; a live Codex run is not covered |
| Driver | not applicable: no driver-specific code |
| Coordination | not applicable: no wave, mailbox or registry code |
| CI provider | not applicable: no pipeline or CI-status code |
| Project state | will test: the fallback lane through stubbed make and uv, the runner lane through its stubbed JSON; not covered: bash 3.2 and BSD awk |
