# Flow run record - issue #1371

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=7bd97216ea674319b817725d7b160d04 -->
## Run 1

- Run-id:            7bd97216ea674319b817725d7b160d04
- Run-start:         f022a2a31371279b67c9508cfe4fe7599c4f8d3f
- Issue:             #1371
- Base SHA:          f022a2a3
- Necessity verdict: Still needed (unblocked by the skillc #288 decision, ANSWERED WITH LIMITS)
- Approval:          granted (GATE: GO-WITH-CONDITIONS, orchestrator outbox rev 16)
- Approver:          cpp-group orchestrator (cpp-orch), authority-model=orchestrator-only, policy rev 1
- Recorded at:       2026-10-23T18:20:00Z

### Section B evidence
skillc#288 6371627281 (decision) and 6371616650 (brief); skillc#279 6364683161 (5/5, CPP ca3030d, skillc 1994c73);
skillc#529 6371486408 (D3 2/2, CPP 652c0118, approval skillc ab2fa36, profile skillc d846a693). PRs since 2026-10-06:
#1529 #1535 #1545 #1546 #1548 #1549 (none records the decision). Draft PR #1393 is superseded (its caveats are stale).
Children #1366/#1368/#1369/#1370 are closed. check-behavioral-eval.py reads an absent dir; nothing encodes the decision.

### Section C - the approved plan
1. `docs/decisions/0011-flow-check-eval-enrollment.md` - ADR, decision ADVISORY: the four skillc limits, the non-test fields, the PENDING Fisher fields as UNPROVEN, the two-arm review trigger, stale/expiry, no threshold, the #1084 reconciliation, citations with URLs and pinned shas; supersedes draft #1393 with credit
2. `docs/measurements/eval-enrollment/flow-check.json` - the decision record (advisory, live-single-arm evidence, the limits, the review trigger, evaluated_content_digest, review_by 2027-01-21 with its reversal trigger beside it)
3. `scripts/check-eval-enrollment.py` - the consumer: advisory-current, stale(content), stale(aged), failing, fixture, unknown; refuses a threshold and an unproven blocking decision; --advisory never fails; non-advisory exit codes distinguish the states
4. `tests/test_eval_enrollment.py` - valid, failing, unknown, stale-content, stale-aged, fixture-only, threshold and blocking refusals, and the exit codes; each red on a mutant
5. `controls/check-eval-enrollment/control.json` - the registered negative control (cases, run-case, a constructed anchor)
6. `Makefile` - eval-enrollment-check target in verify, with its verify-coverage line
7. `.woodpecker.yml` - an advisory step in the per-check pattern
8. `docs/scripts.md` - the inventory entry
9. `docs/decisions/0008-instrument-negative-control-bound.md` - the census row
10. `.gitignore` - a negation for docs/measurements/eval-enrollment/*.json
Scope: 10 files, about 650 lines. Risk: four gate registrations; a content change to flow-check reads STALE (content) right after any such merge (intended).
