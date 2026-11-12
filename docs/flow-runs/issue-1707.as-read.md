<!-- flow-run n=1 id=64ca788da23246a7a4a5946b3be26e0b -->
## Run 1 - issue #1707 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1707
- Read at:      2026-11-12T02:34:47Z
- updatedAt:    2026-11-11T23:07:33Z   (context only - moves on comments and labels)
- Body digest:  bc6793fda14f9e4b38fd4a2f049a183d769d17bfcf86e4d0c35bc7545d2bdbb7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3109 of 3109 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 4 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
The finish gate's counter-model enrolment loop returns the first matching `ran` receipt in filename order. On a branch with more than one receipt that is the oldest, so the gate can pass on a receipt that does not cover this head, and the provenance it prints is the wrong one. A related report: enrolment keys on the branch name, so the same reviewed commit republished under another branch reds CI.

## Findings (4)
- [seq 558](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6301794567), 2026-10-20, medium (stated): flow-finish-gate counter-model enrolment accepts first (oldest) matching receipt, not one covering this diff. Status at origin/main `f63dc946`: flow-finish-gate.sh:688 loops receipts in glob order and returns on the first branch+ancestor match; no run-start or newest check seen.
- [seq 590](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6401643356), 2026-10-25, low (estimated): flow-finish-gate counter-model enrolment returns the first (oldest) matching ran receipt in glob order. Status at origin/main `f63dc946`: Loop at scripts/flow-finish-gate.sh:688-737 still sorts by filename ascending and returns at the first matching ran receipt (CM_ENROLMENT_RECEIPT_FILE).
- [seq 599](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6414884947), 2026-10-26, low (estimated): counter-model enrolment keys on branch name: same reviewed SHA republished under another branch reds CI. Status at origin/main `f63dc946`: Loop at scripts/flow-finish-gate.sh:690-693 still skips receipts whose branch field differs from --branch; message still says 'no receipt for branch'.
- [seq 705](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6733437804), 2026-11-09, low (estimated): flow-finish-gate.sh enrolment loop returns first matching receipt in filename order, so displayed provenance can be a superseded receipt. Status at origin/main `f63dc946`: Loop at flow-finish-gate.sh:688 returns on first matching receipt (CM_ENROLMENT_STATE=receipt) with no newest selection.

## Acceptance
- With two receipts on a branch, enrolment selects the one whose reviewed head is this head or its nearest ancestor, and a committed case shows the old selection failing.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Constraint
Freeze (#1673): fixes only, no new feature under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/`. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is by default; a change to one needs a coordination issue in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before the PR merges.

Parent: #1690 (child of #1673)


<!-- end of body -->
