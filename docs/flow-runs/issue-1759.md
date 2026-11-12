# Flow run record - issue #1759

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=2e97b7e7b04049379beafd5d88969a7d -->
## Run 1

- Run-id:            2e97b7e7b04049379beafd5d88969a7d
- Run-start:         5d7a9d5918b0b4c6f50e77a524218badea015c27
- Issue:             #1759
- Base SHA:          5d7a9d59
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 67: "GATE: GO-WITH-CONDITIONS #1759"
- Recorded at:       2026-11-12T06:00:00Z

### Section B evidence
- commits, merged or open PRs, or other issues addressing this: none
- read at origin/main: deploy.md validates TARGET at Step 3, runs `python -m lib.cicd run --plan deploy` with no target at Step 4b, skips Step 5 (`make "$TARGET"`) whenever the runner ran, and logs TARGET; the deploy plan's last step is the literal `make deploy` (lib/cicd/steps.py)
- /flow:auto Step 9 (auto.md lines 1420-1444) tests `grep -q "^deploy:" Makefile` and runs the literal `make deploy` itself; it passes no target, so automatic runs were never affected
- not reproduced by running the command: running it deploys something
- coordination issues filed by the orchestrator before any edit: kyle #2369, skillc #711, kyle-candidate #13

### Conditions attached to the approval
1. A required test reads the REAL deploy plan and asserts its last step is the literal `make deploy`.
2. The executed test covers four rows (runner found and not found, default and other target), asserting which marker exists and which does not; red on main for the non-default target with the runner found; the log line carries the status of the command that ran.
3. The security gate is shown to run on the non-default path by running the block with the gate stubbed to record its call; measure what the fallback gate line does where CPP is not at ~/Projects/claude-power-pack and file a silent skip as its own issue.
4. deploy.md stays at 1,561 words; equal trim recorded before removal; independent old-versus-new read; whichever of this and #1712 PR ONE merges second re-syncs and re-runs both deploy tests.
5. The PR says at the top what was wrong, that it was read and not run, that /flow:auto Step 9 was never affected, and what a non-default target loses.
6. Exact lane names; full suite before the first gate; two passes, ask before a third.

### Section C - the approved plan
1. `.claude/commands/flow/deploy.md` - the runner block runs only when TARGET is exactly `deploy`; the fallback is the path for every other target and for a host with no runner
2. `tests/test_flow_deploy_target.py` - the document's own blocks run in order on four rows, with marker files; the real plan's last step is pinned
3. `docs/commands-reference.md` - the trimmed text, recorded in a commit before removal
4. `CHANGELOG.md` - entry under behaviour changes
Scope: 4 files, about 150 lines.
Risks: the runner in the executed test is a stand-in; a non-default target loses the runner's bootstrap check and execution record.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: no path-dependent behaviour |
| Harness | not covered: no Codex-driven deploy is run |
| Driver | not applicable |
| Coordination | not covered: no Kyle run |
| CI provider | not applicable |
| Project state | will test: a host where the runner is found and one where it is not, each with the default target and with another target |
| Reader: an agent following /flow:deploy with a target | will test: the document's own blocks run in order; its reading of the prose around them is not covered |
| Reader: /flow:auto Step 9 | not applicable: it runs `make deploy` itself and passes no target |
