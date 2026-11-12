# Flow run record - issue #1705

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=5e4930f893e14728a662bfb8cd3c998a -->
## Run 1

- Run-id:            5e4930f893e14728a662bfb8cd3c998a
- Run-start:         3eaf643dbbc4fc38f5fbe947e5a45e79ff2c9b2b
- Issue:             #1705
- Base SHA:          3eaf643dbbc4fc38f5fbe947e5a45e79ff2c9b2b
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, authority model orchestrator-only), by mailbox rev 17 to role cpp-1508 at 2026-11-11T20:49:33-05:00: "GATE: GO-WITH-CONDITIONS #1705" (assignment a1705-1707-583-g3)
- Recorded at:       2026-11-12T01:49:57Z

### Section B evidence
- Reproduced 2026-11-12 with a minimal script of the same shape under bash 5.2.21: killed through `timeout -s TERM` and `-s INT`, the EXIT trap printed 0 while the process status was 124 (143, 130).
- The trap is unchanged at 3eaf643d: `trap '_gate_on_exit "$?"' EXIT`, with no signal trap in the script. PRs #1722 and #1733 did not touch it.
- Related: #1690 (rollover parent), #1673 (freeze; a defect fix). No duplicate: Nit Store rows 579, 588 and 656 are one defect.
- Coordination issues filed by the orchestrator before merge: cooneycw/kyle #2359, cooneycw/skillc #705, cooneycw/kyle-candidate #8.

### Section C - the approved plan
Rulings: Option 1 (signal traps that re-raise; the single-pid kill latency is accepted and stated); SIGHUP included (129); the helper family goes to Nit Store #1725 as one low comment.

Conditions: the process still dies BY the signal, asserted for TERM, INT and HUP, in both delivery modes for TERM and INT, and `timeout` still reports 124; the marker is printed exactly once and last on stderr, the handler is re-entrant-safe, and a second signal during the handler is tested if it can be produced deterministically, else named as not covered; a registered control whose bad case is red against the pre-fix anchor, verified with --control; the latency stated in the header --help prints and on the docs page with the measured numbers; the coordination status-file path pinned with the existing supervisor tests; make lint and make typecheck; two review passes at most without asking; no push without the merge slot.

1. `scripts/flow-finish-gate.sh` - TERM, INT and HUP traps beside the EXIT trap: report 128 plus the signal number through the existing exit handler once, then restore the default disposition and re-send the signal; the latency note in the header.
2. `tests/test_flow_finish_gate.py` - tests that kill a running gate and assert the marker, its position and count, the wait status and the temp-file cleanup; red on the pre-fix script.
3. `controls/flow-finish-gate-interrupted/control.json` - the registered negative control.
4. `controls/flow-finish-gate-interrupted/run-case.sh` - its case runner.
5. `controls/flow-finish-gate-interrupted/anchors/pre-1705-flow-finish-gate.sh` - the pre-fix script, blind to the bad case.
6. `docs/scripts/flow-finish-gate.md` - one inventory line with the latency numbers.

Scope: about 20 lines of script, about 100 lines of tests, one new control (case directories under `controls/flow-finish-gate-interrupted/cases/`, and the census or coverage registrations if the registration checks require them).

Risks: a signal trap is deferred while bash waits on a foreground child, so a kill of the gate's pid alone takes effect when the current step ends (measured 1.0s before, 6.0s after, with a 6-second child; `timeout` and group kills unaffected); a backgrounded non-interactive gate has SIGINT ignored on entry and cannot trap it; the same stale-marker defect exists in 12 other helper scripts and is not fixed here.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: linked worktree; the fix does not depend on checkout layout |
| Harness | will test: Codex mirrors rebuilt and tests/test_codex_skill_sync.py; a live Codex run is not covered |
| Driver | not applicable: every driver calls the same script |
| Coordination | will test: without Kyle for real; with Kyle through the stubbed supervisor tests, including the status-file path; a live fleet is not covered |
| CI provider | not applicable |
| Project state | will test: the runner lane with a stub runner that sleeps; not covered: bash 3.2 on macOS |
