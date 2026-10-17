<!-- flow-run n=1 id=bb46557005bf470ea11851edebd8e1dc -->
## Run 1 - issue #1452 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1452
- Read at:      2026-10-17T00:11:39Z
- updatedAt:    2026-10-16T22:10:18Z   (context only - moves on comments and labels)
- Body digest:  40118c6648e4abbb3ba191a58bd6a5878565d82afcaaf17187398a1dd928b327   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1543 of 1543 (cap 16384)

### Body as read
**Split from #1400 (bullet 1).** Refs #1400, Refs #864.

## Problem

Nothing guarantees that a counter-model review which actually ran leaves a receipt. Three reviews in the `codex-conversion` wave (#1165, #1166, #1162) ran, were triaged and fixed, and wrote no receipt. Their thread ids exist only in PR bodies (Nit Store comment https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5758216821). `counter-model-uniformity-check.py` then counts a population that is smaller than the reviews that ran.

## Why it is its own issue

Two decisions come before the code:
1. **Enforcement point.** One option is the finish gate refusing a PR whose branch shows a review thread (for example a `CODEX_REVIEW_MODEL` marker or a codex rollout for the branch's range) but no receipt. Another is `/codex:code_review` writing the receipt itself. The second would change who owns the receipt, which `/flow:auto` Step 6 owns today.
2. **The three historical reviews.** Retroactive receipts would name merged SHAs, and #1171's coverage rule refuses that range as retroactive. The choice is between recording them as schema-2 receipts with historical ranges and leaving them as PR-body citations. The Nit Store comment names this as an orchestrator call.

## Acceptance

- A review that ran on a branch, with no receipt for that branch, is reported by a gate that lets work through. That gate gets a committed negative control: the input is a branch with a review thread and no receipt.
- A recorded decision on the three historical reviews.

