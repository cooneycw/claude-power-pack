<!-- flow-run n=1 id=7c7a28fa2c2144e2a12de508f652e2cb -->
## Run 1 - issue #1700 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1700
- Read at:      2026-11-12T06:51:15Z
- updatedAt:    2026-11-12T06:48:08Z   (context only - moves on comments and labels)
- Body digest:  dae7b7034de1ee54c9a2fc01e28dcf70156ab685c2e1f456d83e32031b6cba70   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2736 of 2736 (cap 16384)

### Body as read
## Problem
A counter-model review that honestly ran more than 3 passes has no truthful record, so the finish gate can only report `FLOW_FINISH_GATE: fail (counter-model line missing)` for it.

- `scripts/counter-model-receipt.py`: `PASSES_HARD_CEILING = 3`; `write` refuses `--passes` above it and says to escalate.
- `scripts/flow-finish-gate.sh` (`cm_enrolment_evaluate`): the only passing states are a `ran` receipt or a `skipped` receipt whose reason is in the committed set (`codex-absent`, `reviewer-unavailable`). Neither is true for a review that ran 5 passes.
- So the worker's choices are: write a false pass count (forbidden, and worse than no receipt), write a false skip reason, or ship with the gate red and an explanation in the PR body.

**Severity: medium.** It is not a wrong verdict; the gate fails closed. The harm is the third choice becoming routine: a finish gate that is red "for a known reason" is read by a human or an orchestrator who then waves the red through, which is exactly the habit a gate exists to prevent. On a repo whose CI runs enrolment mode the same PR could not merge at all.

Sightings (cooneycw/kyle, wave kyle-cli):
- kyle #2287 / PR #2292, 2026-11-10: 5 passes, 10 real findings; no receipt, escalation recorded in the PR body by orchestrator ruling.
- kyle #1733 / PR #2338, 2026-11-11: 5 passes; same position. Its sibling branch (#2306, 1 pass) showed the gate's six steps SUCCESS and the verdict fail on this line alone until a receipt was committed.

## Proposed (plan first)
A third truthful record: an **escalated** receipt. It states the real pass count (above the ceiling), the accepted findings, the last clean pass and its head, and WHO ruled that the loop had converged (an orchestrator or the owner, by name and message reference). The gate reads it as its own state and line (`escalated: 5 passes, ruled by <who>`), passing finish mode and enrolment mode, and visibly different from `receipt:`.
The ceiling's purpose (flag a review loop that is not converging) is kept: an escalated receipt cannot be written without the ruling fields, and a count above some outer bound still refuses.

## Acceptance
- A 5-pass review with a recorded ruling writes a receipt and the gate passes with the `escalated:` line.
- Red cases, committed: an escalated receipt with no ruling is refused; `--passes 5` without the escalation still refuses as today; a `ran` receipt claiming 3 passes is unaffected.
- The corpus reader that counts passes treats escalated receipts as their real count.

## Context
Belongs with the gate-path simplification (#1692) if that is rewriting this section; otherwise stands alone. Found while orchestrating kyle #2338. Refs #1495 (where the ceiling came from).


<!-- end of body -->
