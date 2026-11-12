# Flow run record - issue #1707

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=64ca788da23246a7a4a5946b3be26e0b -->
## Run 1

- Run-id:            64ca788da23246a7a4a5946b3be26e0b
- Run-start:         e2c0d037343d39e41dfade1e6dafa4c48684b789
- Issue:             #1707
- Base SHA:          e2c0d037343d39e41dfade1e6dafa4c48684b789
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, authority model orchestrator-only), by mailbox rev 22 to role cpp-1508 at 2026-11-11T21:36:13-05:00: "GATE: GO-WITH-CONDITIONS #1707" (assignment a1705-1707-583-g3)
- Recorded at:       2026-11-12T02:36:34Z

### Section B evidence
- Reproduced 2026-11-12 in a scratch repository with the gate from main a88aafdd, `--enrolment-only`: two `ran` receipts on one branch, the gate names and passes on the OLDER one with HEAD at the newer one's commit; the same with HEAD on a third unreviewed commit; a detached HEAD with no branch given is satisfied by a receipt recorded for another branch name; with `--branch`, as CI passes it, the same input reads missing.
- Nothing since filing touches the selection loop: PRs #1722 and #1733 left `cm_enrolment_evaluate` alone; #1705 is in the EXIT trap.
- Related: #1700 and #1710 (same function, to follow as their own PR), #1171, #1452, #1082. No reader of the gate's counter-model line in kyle or skillc (searched by the worker and by the orchestrator).

### Section C - the approved plan
Rule: among the receipts that pass today's filters unchanged (branch narrowing when a branch is known; recorded head is HEAD or an ancestor), take the one whose head is nearest to HEAD by commit count, ties at one head broken by the latest filename; then apply the existing status judgement to that one receipt. Not a ruling-2 change: no name, shape, state or exit code moves.

Conditions: the control's new bad case is the fail-open one (an older valid ran receipt and a nearest unusable receipt; old selection green, new selection red; pre-fix script as blind anchor; verified with --control), and the orchestrator is told before a second control is invented; all four orderings tested, plus three receipts where the nearest by count is not the latest by filename; an uncomputable count loses to a computable one, and the all-uncomputable case is stated and tested without falling back to first-match; the detached, branch-less limit is stated on the docs page and on the issue; main is merged in after #1705 lands and before the gate; make lint and make typecheck; two review passes at most without asking; no push without the merge slot. Row 599 is declined under #1707 and carried to #1700/#1710 as a question.

1. `scripts/flow-finish-gate.sh` - `cm_enrolment_evaluate`: collect the matching receipts, choose the nearest, then judge it.
2. `tests/test_flow_finish_gate.py` - the orderings, the tie-break, the late-written receipt for an older head, the uncomputable-count cases.
3. `controls/counter-model-enrolment/control.json` - register the fail-open bad case.
4. `docs/scripts/flow-finish-gate.md` - one inventory line, with the detached limit.

Scope: about 30 lines in one function, about 100 lines of tests, one control case (a case directory under `controls/counter-model-enrolment/cases/`, and an anchor if the control's existing one is not blind to it).

Risks: a shallow clone, where a count cannot be computed; two receipts for the same head with different statuses (the later filename wins); the ancestry weakening stays, so a receipt at an ancestor still satisfies commits made after the review.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: temporary repositories, attached and detached; linked worktree by this run |
| Harness | will test: Codex mirrors rebuilt and tests/test_codex_skill_sync.py; no live Codex run |
| Driver | not applicable |
| Coordination | not applicable: enrolment is evaluated before the supervisor path |
| CI provider | will test: the `--enrolment-only --branch` form CI uses, in a temporary repository; a live pull_request pipeline by this PR's own CI |
| Project state | will test: no receipts directory still reads not-enrolled; shallow clone through the existing control cases; not covered: bash 3.2 |
