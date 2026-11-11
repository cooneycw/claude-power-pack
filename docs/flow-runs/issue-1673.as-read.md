<!-- flow-run n=1 id=43badc4cc1534b3ca3d743aa340e7d62 -->
## Run 1 - issue #1673 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1673
- Read at:      2026-11-11T21:50:29Z
- updatedAt:    2026-11-11T14:58:30Z   (context only - moves on comments and labels)
- Body digest:  b6f70b542ade85e1b20ae4de4f74d1457776cd117180123d9f50d407c315d319   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1823 of 1823 (cap 16384)

### Body as read
Tier: 3

Source: owner-requested methodology review, 2026-11-11, measured on origin/main at 31fe6a69 against the last commit before 2026-09-12. Owner approved filing.

## Outcome
Reduce the amount of machinery in the two areas that generate the most repair work, and return the Nit Store to a readable inbox.

Measured, 2026-09-12 to 2026-11-11:
- 429 merged PRs: 244 titled fix, 98 feat (about 2.5 fixes per feature), 1 revert.
- Scoped fix titles by area: flow 32, cicd 27, tests 12, cpp-init 9, counter-model 8, codex 8, flow-wave 6, flow-wave-mailbox 5.
- Median PR was 633 changed lines and merged about 10 minutes after opening.
- Test files grew from 97 to 401.
- Nit Store #864 holds 708 comments (438 in September, 209 in October, 61 so far in November).

Caveat: a fix title is not proof of a defect in earlier work, some are hardening. The ratio is a prompt to look, not a verdict.

## Acceptance
- A wave scoped to `flow` and `cicd` whose changes delete, merge or simplify code paths. No new features land in those two areas while it runs.
- Wave close reports, before and after: line counts for those areas, and the fix:feat ratio for the following 30 days as a follow-up reading.
- #864 backlog is aggregated into real issues or explicit dispositions, #864 is closed, and a successor Nit Store is opened. From then on the Nit Store rolls over monthly. Every place that names #864 (the owner's global directives, CLAUDE.md, command documents) is updated in the same change, or the number is resolved by search and not hard-coded.

## Constraint
Run after the word-budget, mirror, census and script-index issues filed alongside this one, so the wave works on the smaller surface.

## Assumption
That the wave should be an epic with child issues chosen at planning. This issue does not pre-pick what to delete.


<!-- end of body -->
