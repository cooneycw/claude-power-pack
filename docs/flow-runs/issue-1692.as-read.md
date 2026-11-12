<!-- flow-run n=1 id=b5545e7430c2453e840727dcc0dae876 -->
## Run 1 - issue #1692 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1692
- Read at:      2026-11-11T22:53:16Z
- updatedAt:    2026-11-11T22:33:52Z   (context only - moves on comments and labels)
- Body digest:  04c26423c62d8765f4fe050a65af484111084c9b0790abb82e412179128f47d3   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2978 of 2978 (cap 16384)

### Body as read
Tier: 2

Source: child of #1673, chosen at that epic's planning run on 2026-11-11 from the fix-commit counts in `docs/measurements/simplification-wave-baseline-2026-11.md` (lands with the #1673 planning PR).

## Outcome
The quality gate (the step that runs lint, tests and checks before a commit) is split between a shell wrapper and a Python runner, and together they are the most repaired code in `cicd`. Reduce the number of paths a gate run can take.

Measured on `origin/main` at `15521b1e`, fix-titled commits since 2026-09-12:

| File | Lines | Fix commits |
|---|---|---|
| `lib/cicd/runner.py` | 2,074 | 18 |
| `lib/cicd/steps.py` | 1,869 | 14 |
| `scripts/flow-finish-gate.sh` | 1,796 | 13 |
| `lib/cicd/outcomes.py` | 637 | 8 |

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
- The gate's verdict lines and exit codes are read by command documents and by other repositories. CPP is intrinsically linked to kyle and skillc, so they are promised behaviour and the default is to leave them exactly as they are.
- **Owner ruling, 2026-11-11:** they MAY change where there is sufficient reason, and the constraint is not meant to hold back progress. The condition is that a coordination issue is filed, marked urgent, in each of `cooneycw/kyle`, `cooneycw/skillc` and `cooneycw/kyle-candidate`, naming what changes, the old and new form, and the CPP change that carries it. File them before the CPP change merges and link them from this issue's plan and PR. The reason for the change is stated in the plan the owner approves.
- Read the `flow`/`cicd` bucket of #1690's disposition list if it exists when this starts. It is input, not a blocker.

Parent: #1673




<!-- end of body -->

<!-- flow-run n=2 id=1a33605b47f94cf08659e9324a1d196b -->
## Run 2 - issue #1692 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1692
- Read at:      2026-11-12T00:31:59Z
- updatedAt:    2026-11-12T00:31:51Z   (context only - moves on comments and labels)
- Body digest:  04c26423c62d8765f4fe050a65af484111084c9b0790abb82e412179128f47d3   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2978 of 2978 (cap 16384)

### Body as read
Tier: 2

Source: child of #1673, chosen at that epic's planning run on 2026-11-11 from the fix-commit counts in `docs/measurements/simplification-wave-baseline-2026-11.md` (lands with the #1673 planning PR).

## Outcome
The quality gate (the step that runs lint, tests and checks before a commit) is split between a shell wrapper and a Python runner, and together they are the most repaired code in `cicd`. Reduce the number of paths a gate run can take.

Measured on `origin/main` at `15521b1e`, fix-titled commits since 2026-09-12:

| File | Lines | Fix commits |
|---|---|---|
| `lib/cicd/runner.py` | 2,074 | 18 |
| `lib/cicd/steps.py` | 1,869 | 14 |
| `scripts/flow-finish-gate.sh` | 1,796 | 13 |
| `lib/cicd/outcomes.py` | 637 | 8 |

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
- The gate's verdict lines and exit codes are read by command documents and by other repositories. CPP is intrinsically linked to kyle and skillc, so they are promised behaviour and the default is to leave them exactly as they are.
- **Owner ruling, 2026-11-11:** they MAY change where there is sufficient reason, and the constraint is not meant to hold back progress. The condition is that a coordination issue is filed, marked urgent, in each of `cooneycw/kyle`, `cooneycw/skillc` and `cooneycw/kyle-candidate`, naming what changes, the old and new form, and the CPP change that carries it. File them before the CPP change merges and link them from this issue's plan and PR. The reason for the change is stated in the plan the owner approves.
- Read the `flow`/`cicd` bucket of #1690's disposition list if it exists when this starts. It is input, not a blocker.

Parent: #1673




<!-- end of body -->

<!-- flow-run n=3 id=38e309fe078b46d3a826d5b356b86ad6 -->
## Run 3 - issue #1692 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1692
- Read at:      2026-11-12T04:06:02Z
- updatedAt:    2026-11-12T00:35:18Z   (context only - moves on comments and labels)
- Body digest:  04c26423c62d8765f4fe050a65af484111084c9b0790abb82e412179128f47d3   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2978 of 2978 (cap 16384)

### Body as read
Tier: 2

Source: child of #1673, chosen at that epic's planning run on 2026-11-11 from the fix-commit counts in `docs/measurements/simplification-wave-baseline-2026-11.md` (lands with the #1673 planning PR).

## Outcome
The quality gate (the step that runs lint, tests and checks before a commit) is split between a shell wrapper and a Python runner, and together they are the most repaired code in `cicd`. Reduce the number of paths a gate run can take.

Measured on `origin/main` at `15521b1e`, fix-titled commits since 2026-09-12:

| File | Lines | Fix commits |
|---|---|---|
| `lib/cicd/runner.py` | 2,074 | 18 |
| `lib/cicd/steps.py` | 1,869 | 14 |
| `scripts/flow-finish-gate.sh` | 1,796 | 13 |
| `lib/cicd/outcomes.py` | 637 | 8 |

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
- The gate's verdict lines and exit codes are read by command documents and by other repositories. CPP is intrinsically linked to kyle and skillc, so they are promised behaviour and the default is to leave them exactly as they are.
- **Owner ruling, 2026-11-11:** they MAY change where there is sufficient reason, and the constraint is not meant to hold back progress. The condition is that a coordination issue is filed, marked urgent, in each of `cooneycw/kyle`, `cooneycw/skillc` and `cooneycw/kyle-candidate`, naming what changes, the old and new form, and the CPP change that carries it. File them before the CPP change merges and link them from this issue's plan and PR. The reason for the change is stated in the plan the owner approves.
- Read the `flow`/`cicd` bucket of #1690's disposition list if it exists when this starts. It is input, not a blocker.

Parent: #1673




<!-- end of body -->
