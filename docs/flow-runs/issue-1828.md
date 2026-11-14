# Flow run record - issue #1828

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=27a4106219a0480c81ba6e6d810246f7 -->
## Run 1

- Run-id:            27a4106219a0480c81ba6e6d810246f7
- Run-start:         908d332c0c2df04c1540fbb0afab5ad96e8db8c7
- Issue:             #1828
- Base SHA:          908d332c0c2df04c1540fbb0afab5ad96e8db8c7
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          owner (cooneycw), in-session "approved." after Section C plus lane and reader rows
- Recorded at:       2026-11-14T18:37:58Z

### Section B evidence
- PR #1808 (65921ba3, closes #1807): fixture-owned admission state for run-case.sh, _gate_env/_run, test_cpp_environment_preservation.py, test_cpp_runner_runtime.py, test_silent_test_success.py.
- PR #1782 (5e5396f1): allowlisted gate environment.
- Measured 2026-11-14 on this host with admission ON and no kyle-lock on PATH: test_flow_finish_gate.py + test_cpp_environment_preservation.py + test_cpp_runner_runtime.py 232 passed; resume-control test 4 passed; make negative-controls 136 PASS exit 0. Part B acceptance is already met; its red is no longer reproducible.
- Other merged PRs since filing: #1826, #1827, #1819, #1820 (none touch this seam).
- Issues: #1807 (closed, the B fix), #1725 (Nit Store source). No superseding issue.
- Host sibling worktrees: none with unpushed commits touching the planned paths.

### Section C - the approved plan
1. `scripts/flow-finish-gate.sh` - A1: pass --purpose "cpp finish gate: <owner/repo> <branch> <short-sha>" (omit underivable parts), --issue from an issue-<N>- branch, --pr from a bounded gh pr view; A2: kyle-lock exit 10/11 with no recorded status prints "no grant within ${wait}s (last state: queued|frozen), no gate work started"; verdict unchanged.
2. `tests/test_flow_finish_gate.py` - argv-recording fake kyle-lock test for purpose/issue; exit 10 and 11 message tests; a derivation test that every variable the gate and admission helper read is in _GATE_KNOBS or the allowlist.
3. `docs/scripts/flow-finish-gate.md` - one entry for lease identity and the queued/frozen message.

Scope: 3 files, ~120 lines.
Risks: gh pr view adds a network call before queueing (bounded by timeout, skipped without gh); --issue/--pr must be integers or kyle-lock exits usage (regex-checked).

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | not applicable - identity is derived from origin and HEAD, identically in a main checkout and a worktree |
| Harness | not applicable - a shell helper, no command document or Codex mirror changes |
| Driver | not applicable - every driver invokes the same gate script |
| Coordination | will test - stubbed kyle-lock records argv and exits 10/11; without-Kyle path unchanged and already covered; a live Kyle fleet is not covered (real client argparse and acquire body read instead) |
| CI provider | not applicable - no CI output is read |
| Project state | will test - no origin, detached HEAD, non-issue branch: underivable parts are omitted and the run does not error |
| Toolchain version | not applicable - no toolchain dependency added |
| Clone shape | not applicable - only HEAD's short sha is read |
| Run location | will test - a run outside any checkout still passes a purpose, with no repo or branch |
| Gate target | not covered - admission is a host decision; this does not touch whose toolchain runs |
| Wave role state | not applicable - no wave state involved |
| Reader: Kyle lease authority (kyle-lock acquire body) | will test - fed a stub, not the real authority; the real argparse (int --issue/--pr) and body were read |
| Reader: owner via kyle-lock status | not covered - not exercised end to end |
| Reader: operator and /flow:auto report reading the FAIL line | will test - prefix and exit code asserted unchanged; no sibling-repo parser of the changed text (searched kyle, skillc, kyle-candidate) |
