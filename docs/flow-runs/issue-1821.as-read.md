<!-- flow-run n=1 id=daff6dbf76224a8abff25c94f7c98a1d -->
## Run 1 - issue #1821 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1821
- Read at:      2026-11-14T16:31:02Z
- updatedAt:    2026-11-14T16:29:40Z   (context only - moves on comments and labels)
- Body digest:  ab21f067fddce86b0aba75058a10ac6a416b559f2da73626a65c0d9c4559f727   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2413 of 2413 (cap 16384)

### Body as read
## Problem

The close-time lane check (`lanes_at_close` in `scripts/flow-plan-record.py`) decides whether an approved plan's `will test` lanes were demonstrated. It is a check that lets work through; nothing after it works the answer out again. It has two false greens, both reproduced:

1. **Old-run evidence satisfies a new run.** `demonstrated_rel()` (`scripts/flow-plan-record.py:1077`) returns the same file for every run of an issue (`docs/flow-runs/issue-{N}.lanes-demonstrated.md`). The check (around line 1169) reads its rows without checking which run or plan produced them. Reproduced: run 2 got no missing-evidence warning from run 1's unchanged results. Removing those results brought back `LANES NOT DEMONSTRATED (2)`.
2. **Deleting the lane file erases the plan's promises.** `if project_lanes(root) is None: return LanesAtClose("nothing-owed")` (line 1146) runs before the approved plan is read. A plan approved with `will test` lanes owes nothing once `.claude/lanes.md` is removed. Reproduced: the warning disappeared after deletion. `tests/test_flow_plan_record_lanes.py:861` (`test_from_a_linked_worktree_the_lane_file_read_is_the_worktrees_own`) currently requires this behaviour, so the fix needs a policy change.

## Proposed fix (one mechanism for both)

- At approval, record in the run's section that the project uses lanes, the lanes owed, and a digest of the approved plan.
- At close, work out the obligations from that approval record, not from the lane file as it stands now. A project that never adopted lanes keeps today's silence.
- Tie demonstration records to the current run ID and the approved-plan digest. Rows for another run or digest do not count. Either key the file per run, or put a run/digest header in it and check that header.

## Acceptance

- Run 2 with run 1's unchanged demonstration file reports `LANES NOT DEMONSTRATED (n)`.
- Deleting `.claude/lanes.md` after approving a plan with `will test` lanes still reports the owed lanes.
- A project with no lane file at approval stays silent, as it does today.
- Each item above has a committed red case: the input that made the old code give the wrong verdict.
- The test at line 861 is changed to the new policy, with the reason for the change stated.

## Source

From an external review of d90712ee (11.1.1), relayed by the owner on 2026-11-14. Both line references were checked against d90712ee before filing.


<!-- end of body -->
