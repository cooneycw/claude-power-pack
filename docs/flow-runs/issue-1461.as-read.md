<!-- flow-run n=1 id=f965b3827b65499d849fe4e1d14a1dc7 -->
## Run 1 - issue #1461 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1461
- Read at:      2026-10-17T02:01:23Z
- updatedAt:    2026-10-17T00:15:07Z   (context only - moves on comments and labels)
- Body digest:  6143a023aa16101847068441bcf5a7db65b29d48712262b2e4da359c58e76213   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1508 of 1508 (cap 16384)

### Body as read
Found while reviewing PR #1457 (merged as fc87b5b; Refs #1400).

## Defect

#1400's closing table (comment 6226138811) marks bullet 3 "Fixed (#1419)", but #1419 fixed only part of it, and no split issue carries the rest.

1. **A read denied mid-review is not detected.** The source nit (#864 comment 5858478984) names "a read denied mid-review (a different path, a policy that changes)". `_mid_run_sandbox_failures` (`scripts/counter-model-receipt.py:391-415`) counts only `exit_code: -1` sandbox-launch failures. It deliberately ignores a command that ran and exited non-zero. Scenario: the pre-run probe passes, so the claim is `full`. Mid-review, `cat other/path` is refused by policy (exit 1, "Permission denied"). The receipt still records `scope: full`. Ignoring a plain non-zero exit may be the right trade-off, since it is ambiguous, but it should be decided on purpose and recorded, not marked "Fixed".
2. **Scope on the receipt is optional, not enforced.** The writer adds `scope` only when supplied (`:607`), and `validate` checks it only when present (`:721`). Only `flow/auto.md:1134` passes `--scope`. A non-delegated ran receipt without it validates and says nothing about scope.

## Why it matters

A receipt saying `scope: full` is read later as evidence that the reviewer saw everything. Here it can say that after a denied read, or say nothing at all.

## Ask

Decide whether ordinary non-zero denials count toward scope. Require `scope` on non-delegated ran receipts, or record why not.

