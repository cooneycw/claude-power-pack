<!-- flow-run n=1 id=b9b2e411f26c49cfb9cad64d0c009e02 -->
## Run 1 - issue #1691 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1691
- Read at:      2026-11-12T05:13:45Z
- updatedAt:    2026-11-12T02:18:38Z   (context only - moves on comments and labels)
- Body digest:  0e077e25318dbcecece2f7e57e677cf37e6ccd4f4be432e0b3b40e19a9bbcb6d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2312 of 2312 (cap 16384)

### Body as read
Tier: 2

Source: child of #1673, chosen at that epic's planning run on 2026-11-11 from the fix-commit counts in `docs/measurements/simplification-wave-baseline-2026-11.md` (lands with the #1673 planning PR).

## Outcome
The wave scripts (the ones that coordinate several worker sessions on one batch of issues) are the largest shell files in the repository and among the most repaired. Reduce how much of them there is.

Measured on `origin/main` at `15521b1e`, fix-titled commits since 2026-09-12:

| File | Lines | Fix commits |
|---|---|---|
| `scripts/flow-wave-registry.sh` | 4,684 | 15 |
| `scripts/flow-wave-mailbox.sh` | 3,517 | 11 |
| `scripts/flow-wave-lexicon.sh` | 1,166 | 5 |

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
- Do not run this inside a `/flow:wave` that depends on the scripts being changed; a live wave reads them from the main checkout.
- Read the `flow`/`cicd` bucket of #1690's disposition list if it exists when this starts. It is input, not a blocker.

Parent: #1673



<!-- end of body -->

<!-- flow-run n=2 id=92f82acff32c4d93992af603363fd658 -->
## Run 2 - issue #1691 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1691
- Read at:      2026-11-12T09:26:06Z
- updatedAt:    2026-11-12T05:29:38Z   (context only - moves on comments and labels)
- Body digest:  20a4629702bd30ec647b41a6e397c7af1d990bd19274e03857201aa0f94107dd   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3098 of 3098 (cap 16384)

### Body as read
Tier: 2

Source: child of #1673, chosen at that epic's planning run on 2026-11-11 from the fix-commit counts in `docs/measurements/simplification-wave-baseline-2026-11.md` (lands with the #1673 planning PR).

## Outcome
The wave scripts (the ones that coordinate several worker sessions on one batch of issues) are the largest shell files in the repository and among the most repaired. Reduce how much of them there is.

Measured on `origin/main` at `15521b1e`, fix-titled commits since 2026-09-12:

| File | Lines | Fix commits |
|---|---|---|
| `scripts/flow-wave-registry.sh` | 4,684 | 15 |
| `scripts/flow-wave-mailbox.sh` | 3,517 | 11 |
| `scripts/flow-wave-lexicon.sh` | 1,166 | 5 |

A fix title is not proof of a defect in earlier work. The counts say where to look, not what to delete.

## Acceptance
**Reframed at planning (orchestrator ruling, 2026-11-12).** The survey read all 10,675 lines of the five wave scripts: about 15 lines of dead code, 55 to 70 of exact duplication, and 257 of movable history, under 3 percent in all, the same place #1693 and #1692 ended. No dead subcommand, no dead flag, no refusal that has stopped earning its place. What the scripts need is to be right in one place (a live process whose main thread exited is read as a dead owner) and true in about thirty (comments and help text that have drifted from the code). So this issue delivers: that fix, an accuracy pass on comments, help headers and the two command documents, the small exact tidy, and tests that pin what was found. The lines below stand for the tidy; a reduction number is not a goal.

- The change deletes, merges or simplifies code paths in the files above. It adds no feature and no new gate.
- The run opens with its own survey naming what will be removed and why it is safe, and that plan is approved before any edit. This issue does not pre-pick what to delete.
- Before and after line counts for the files above are reported from named commits, using the commands in the baseline document. Code moved to another file without being deleted is named as a move, not counted as a reduction.
- Behaviour that callers rely on is unchanged, or each removed behaviour is named with the evidence that nothing uses it.
- An independent old-versus-new read is done before review (owner addition, 2026-11-11): a reader that did not write the change compares the code before and after and lists every behaviour present before and absent or altered after. Each listed item is either restored or named as a deliberate removal with its evidence. The PR states who did the read and what it found, including "found nothing".
- Tests and controls that only pinned removed code are removed with it. A control for a gate that still lets work through stays.

## Constraint
- While #1673 is open, no new feature lands in `flow` or `cicd`.
- Do not run this inside a `/flow:wave` that depends on the scripts being changed; a live wave reads them from the main checkout.
- Read the `flow`/`cicd` bucket of #1690's disposition list if it exists when this starts. It is input, not a blocker.

Parent: #1673




<!-- end of body -->
