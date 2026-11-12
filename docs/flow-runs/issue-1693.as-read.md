<!-- flow-run n=1 id=51f1b2edbe2f4e689b7f725cb57798c1 -->
## Run 1 - issue #1693 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1693
- Read at:      2026-11-12T00:07:32Z
- updatedAt:    2026-11-11T23:07:58Z   (context only - moves on comments and labels)
- Body digest:  346a3e19d6e2a1ee2974b7f75fca02136af0f75071fa9ab51d80c2b8f40e628d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2486 of 2486 (cap 16384)

### Body as read
Tier: 2

Source: child of #1673, chosen at that epic's planning run on 2026-11-11 from the fix-commit counts in `docs/measurements/simplification-wave-baseline-2026-11.md` (lands with the #1673 planning PR).

## Outcome
The last steps of a run (merging the pull request, then removing the scratch checkout) carry many refusal paths added one incident at a time. Reduce them to the ones that still earn their place.

Measured on `origin/main` at `15521b1e`, fix-titled commits since 2026-09-12:

| File | Lines | Fix commits |
|---|---|---|
| `scripts/gh-pr-merge.sh` | 2,235 | 10 |
| `scripts/worktree-remove.sh` | 1,422 | 11 |
| `scripts/flow-worktree-claim.sh` | 566 | 5 |
| `scripts/flow-worktree-sweep.sh` | 580 | not in the top 25 |
| `scripts/flow-worktree-guard.sh` | 399 | not in the top 25 |

A fix title is not proof of a defect in earlier work. The counts say where to look, not what to delete.

## Acceptance
- The change deletes, merges or simplifies code paths in the files above. It adds no feature and no new gate.
- The run opens with its own survey naming what will be removed and why it is safe, and that plan is approved before any edit. This issue does not pre-pick what to delete.
- Before and after line counts for the files above are reported from named commits, using the commands in the baseline document. Code moved to another file without being deleted is named as a move, not counted as a reduction.
- Behaviour that callers rely on is unchanged, or each removed behaviour is named with the evidence that nothing uses it.
- An independent old-versus-new read is done before review (owner addition, 2026-11-11): a reader that did not write the change compares the code before and after and lists every behaviour present before and absent or altered after. Each listed item is either restored or named as a deliberate removal with its evidence. The PR states who did the read and what it found, including "found nothing".
- Tests and controls that only pinned removed code are removed with it. A control for a gate that still lets work through stays.

## Constraint
- While #1673 is open, no new feature lands in `flow` or `cicd`.
- Each refusal exit code in these two helpers guards against losing work or closing the wrong issue. Removing one needs the incident it came from named and the reason it can no longer happen.
- Read the `flow`/`cicd` bucket of #1690's disposition list if it exists when this starts. It is input, not a blocker.

Parent: #1673



<!-- end of body -->
