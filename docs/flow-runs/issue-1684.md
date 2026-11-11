# Flow run record - issue #1684

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=53f932869aa1490f8ea6227204543f86 -->
## Run 1

- Run-id:            53f932869aa1490f8ea6227204543f86
- Run-start:         d79d0042a2daff328eb8c7f5607fdd7fe00d1b60
- Issue:             #1684
- Base SHA:          d79d0042a2daff328eb8c7f5607fdd7fe00d1b60
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner, in the driving session ("approved")
- Recorded at:       2026-11-11T20:43:21Z

### Section B evidence
- commits since 2026-11-11T20:39Z: none touching scripts/flow-ci-status.sh, lib/cicd/flow.py, tests/test_flow_ci_status.py or controls/
- merged PRs that day: #1675, #1676, #1679, #1680, #1681, #1682, #1683 - all merged before the issue was filed; none changes the wait loop
- duplicate/superseding issues: none (#1262, #1604, #1610, #1677 related and closed)
- cause is a reading of the code, not a reproduction: the reported output matches the woodpecker-cli lane's mid-wait re-listing failure; an empty status is a second early exit in the same loops

### Section C - the approved plan
1. `scripts/flow-ci-status.sh` - with --wait, a found pipeline with an unreadable status and a mid-wait listing failure keep polling to the deadline on both Woodpecker lanes; the wait reports expired; a waited run ending unknown or expired exits non-zero
2. `lib/cicd/flow.py` - recorded-provider path: a lane's found-but-unreadable answer no longer ends the wait; expiry exits non-zero
3. `tests/test_flow_ci_status.py` - empty status then success, listing failure then success, expiry exit codes, on the fallback path
4. `tests/test_flow_recorded_providers.py` - the same through recorded dispatch
5. `controls/flow-ci-status-wait/` - new negative control (control.json, run-case.sh, cases, anchor): an empty-status pipeline that later turns green must be polled; the pre-change script returns at once and fails the case
6. `controls/census.md` - add the new control to row 10
7. `.claude/verify-coverage.json` - name the new control in the helper's entry
8. `docs/scripts.md` - one entry for the behaviour change and exit codes

Scope: 8 paths, roughly 250-350 lines, mostly tests and the control.

Risks: exit-code change (an expired wait on a running pipeline exited 0; external callers such as kyle's lock-hold script read it); a persistent listing outage now costs the full wait window; GitHub Actions unknown (all skipped, listing cap) stays final, now non-zero under --wait.

Exit codes: the approval named none, so the recommended pair stands - 2 for unknown, 5 for an expired wait, unchanged without --wait.
