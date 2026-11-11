# Flow run record - issue #1678

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=af6e225ea4d941b0ad4bd04408ad74ee -->
## Run 1

- Run-id:            af6e225ea4d941b0ad4bd04408ad74ee
- Run-start:         dca1ac6bdcb8db2410b6238b470290660d1df364
- Issue:             #1678
- Base SHA:          dca1ac6bdcb8db2410b6238b470290660d1df364
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), interactively in the driving session ("approved")
- Recorded at:       2026-11-11T18:58:09Z

### Section B evidence
- commits: none on origin/main since 2026-11-11T18:49:28Z; none touching scripts/flow-finish-gate.sh, scripts/coordination-admission.sh, controls/flow-finish-coordination, tests/test_flow_finish_gate.py, docs/scripts.md
- PRs: #1675, #1676 merged 2026-11-11 before filing, unrelated; open PRs: none
- dup/super: #864 (Nit Store origin comment); #810, #1261, #1292, #1211 matched the search, closed and unrelated
- siblings: no unpushed commits on these paths in any readable worktree; one worktree UNREADABLE (a scratchpad t008/cpp-pin checkout), unexamined
- kyle: scripts/kyle-lock at 4aa3a2aa has a single --wait deadline covering queued, frozen and unavailable

### Section C - the approved plan
1. `scripts/flow-finish-gate.sh` - pass a bounded `--wait` (CPP_KYLE_LOCK_WAIT_SECONDS, default 3600, positive integer or a named fail) to `kyle-lock run full-suite`; supervisor exit 75 with no gate status prints `FLOW_FINISH_GATE: fail (coordination unavailable: <code>; ...)`; all inside the admission-on block, other exits unchanged
2. `tests/test_flow_finish_gate.py` - regression test with a forever-unavailable fake, held counterpart, invalid-bound test; update fakes that require `$3 == --` and the exit-75 row
3. `controls/flow-finish-coordination/run_case.py` - fake accepts `--wait N`; new `unavailable` mode requires the named verdict
4. `controls/flow-finish-coordination/control.json` - add the `bad-unavailable` case, update limits
5. `controls/flow-finish-coordination/cases/bad-unavailable/mode.txt` - the committed red input
6. `docs/scripts.md` - document the bound, variable, default, verdict, and why one bound covers queued and unavailable

Scope: 6 files, ~120 lines, plus regenerated codex/skills mirrors of item 1.
Risks: a healthy queue longer than the bound now fails (exit 10); exit 75 also covers immediate malformed answers, so "within N s" is an upper bound; exercised against a fake, not the live kyle-lock.
Owner clarification before approval: the change must be inert where the admission flag is off; the new variable is read and validated only inside the admission-on block.
