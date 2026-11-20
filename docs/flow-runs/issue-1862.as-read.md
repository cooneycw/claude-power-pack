<!-- flow-run n=1 id=ba462601dcef4525a733360a24ef3fd9 -->
## Run 1 - issue #1862 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1862
- Read at:      2026-11-20T12:04:01Z
- updatedAt:    2026-11-20T11:59:28Z   (context only - moves on comments and labels)
- Body digest:  b9d0fe1b42af01d0288fe57f5af968d1231a789073e825b3b905a89576eefcd2   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3477 of 3477 (cap 16384)

### Body as read
Tier: 2

## Outcome

Accepting a finding whose fix touches only the plan record does not force another Codex review pass. A re-review is spent only when reviewed code changed.

Today `/flow:auto` Step 6 says "One re-review after the first accepted fix." Adding a lane row or a `Reader:` row to `docs/flow-runs/issue-<N>.md` therefore costs a full review pass (median 516k-649k tokens since 11-15) while changing no behaviour. This is the main mechanism behind passes/issue rising from about 1.9 to 2.8 in CPP.

## Constraints

- The receipt still binds a reviewed head. A commit that changes any path outside the plan-record set still needs the re-review, exactly as now.
- The plan-record path set is closed and named in one place (for example `docs/flow-runs/issue-<N>.md` and its `.as-read.md` snapshot). It is not a glob a later edit can widen silently.
- Kyle and skillc CI validate receipts at the merge boundary. If the validator's head rule changes, that is an interface change: file the coordination issues in kyle, skillc and kyle-candidate before merging (standing owner rule for CPP output those repos read).

## Acceptance

- Negative control, committed: the same branch with one non-plan line added after the reviewed head is refused without a new pass.
- Positive case, committed: a branch whose only post-review commits touch the plan-record files gets a valid receipt without a new pass, and the receipt says the head moved only within those paths.
- `/flow:auto` Step 6 states the rule in one line.

## Proposed approach

Let `counter-model-receipt.py` accept a head beyond the reviewed one when `git diff --name-only <reviewed>..HEAD` falls entirely within the plan-record set, recording both heads. An alternative is a `## Notes` section in the review output that never counts against a clean verdict. That changes the review format and the receipt schema, so it is the heavier option.

Owner decision: removes a review obligation, so it needs the #1850 Q2 ruling.

## Evidence (shared by this issue and its three siblings)

Measured 2026-11-20 from 935 parsed Codex review sessions on the main host (2026-10-16 to 2026-11-20) and 989 committed counter-model receipts across kyle, skillc and claude-power-pack. Same-repo comparisons:

| Repo / period | findings/review | LOW/review | lane+reader findings/review | clean-pass rate | median tokens/review | passes/issue |
|---|---|---|---|---|---|---|
| CPP before 11-11 | 1.35 | 0.15 | 0.12 | 29% | 301k | 1.9 |
| CPP 11-15+ | 2.19 | 0.90 | 0.84 | 13% | 516k | 2.8 |
| skillc before 11-11 | 2.42 | 0.26 | 0.13 | 19% | 369k | 2.9 |
| skillc 11-15+ | 3.98 | 1.11 | 0.89 | 8% | 649k | 3.1 |

Receipt dispositions: CPP accepted 88% → 62% (rejected+deferred 12% → 39%); skillc accepted 98% → 73%.

The rise lines up with the lane clauses in the review prompt (#1704, 2026-11-11) and the reader/stand-in clauses (#1749, 2026-11-12), switching on per repo when `.claude/lanes.md` landed (CPP 11-11, kyle 11-13, skillc 11-15). Prompt size itself is flat. Limits: kyle's recent reviews mostly run in containers and are not in this sample; finding kinds were tagged by keyword. Owner direction is in [discussion #1830](https://github.com/cooneycw/claude-power-pack/discussions/1830) and #1850 (charter, Q2: "already enforced by a helper - delete the prose").

Siblings: #1862 (plan-only re-review), #1863 (drop duplicated review clauses), #1864 (finding kinds), #1865 (review-yield and escaped-defect report).



<!-- end of body -->
