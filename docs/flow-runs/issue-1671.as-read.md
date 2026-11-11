<!-- flow-run n=1 id=29c599b037704e7889141765edf1d4b3 -->
## Run 1 - issue #1671 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1671
- Read at:      2026-11-11T19:50:43Z
- updatedAt:    2026-11-11T14:58:28Z   (context only - moves on comments and labels)
- Body digest:  95df6d74ceb79d39cc4d27bffa556b86345e2c866949cfbb806758d410764213   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1361 of 1361 (cap 16384)

### Body as read
Tier: 2

Source: owner-requested methodology review, 2026-11-11, measured on origin/main at 31fe6a69 against the last commit before 2026-09-12. Owner approved filing.

## Outcome
A decision record should state a decision and rarely change. `docs/decisions/0008-instrument-negative-control-bound.md` is also the instrument census, by design (CLAUDE.md: its membership is derived from `scripts/` and gated by `make instrument-census-check`). The result is that the file did not exist 60 days ago, is now 19,206 words, and was touched by 104 commits in that window, with its mirror at `codex/skills/flow-auto/docs/decisions/` touched 103 times. Almost every PR that adds or changes a checker edits an ADR.

This issue challenges where the census lives, not the bound or the gate.

## Acceptance
- The ADR holds the rule, the bound and its rationale. Adding an instrument no longer edits it.
- The census lives in data. `controls/` already carries 96 `control.json` files; prefer that home over a new one.
- `make instrument-census-check` still reds on an unenumerated instrument. Negative control: the existing known-bad case (a script with no census entry) still fails after the move. Run it before and after and say so.

## Constraint
Readers and tools that cite ADR 0008 by path (the glossary, command documents, cooneycw/skillc fixtures) must keep resolving.


<!-- end of body -->
