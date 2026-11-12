<!-- flow-run n=1 id=5e4930f893e14728a662bfb8cd3c998a -->
## Run 1 - issue #1705 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1705
- Read at:      2026-11-12T01:45:52Z
- updatedAt:    2026-11-11T23:07:31Z   (context only - moves on comments and labels)
- Body digest:  a9b34f5016a2be3dd78a29b87127b11b166dfc279d454165c98ca8ff513444dc   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3209 of 3209 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 3 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
`scripts/flow-finish-gate.sh` prints `FLOW_FINISH_GATE_EXIT=0` when the run is killed by SIGTERM or SIGINT, while the process itself exits 143 or 130. A reader of the log sees a clean exit marker on an interrupted gate. Reported three times. The marker is one kyle reads, so the fix is gated on the owner ruling below.

## Findings (3)
- [seq 579](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6395484211), 2026-10-25, medium (estimated): flow-finish-gate.sh EXIT trap prints FLOW_FINISH_GATE_EXIT=0 for a SIGTERM-interrupted run. Status at origin/main `f63dc946`: scripts/flow-finish-gate.sh:190 only has trap on EXIT reading $?; no INT/TERM trap, so an interrupted run can log a success exit marker. Same defect as seq 588.
- [seq 588](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6401604083), 2026-10-25, medium (estimated): flow-finish-gate.sh EXIT trap reports FLOW_FINISH_GATE_EXIT=0 after SIGTERM of an interrupted gate. Status at origin/main `f63dc946`: Trap at scripts/flow-finish-gate.sh:190 unchanged, no signal path; duplicate of seq 579 with an explicit request for an interrupted-run control.
- [seq 656](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6629711455), 2026-11-04, low (estimated): flow-finish-gate prints FLOW_FINISH_GATE_EXIT=0 when killed by SIGTERM (exit marker disagrees with 143). Status at origin/main `f63dc946`: Only an EXIT trap (line 190); reproduced with a minimal bash script: EXIT trap sees $?=0 after SIGTERM while process rc=124/143. No signal trap.

## Acceptance
- A gate killed by SIGTERM and by SIGINT prints an exit marker that agrees with its real exit status; a test kills a running gate and asserts the marker.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Coordination required before the fix merges
Orchestrator ruling, wave cpp-improvement, 2026-11-11: this is a live correctness defect, so the value may change, and a defect fix is not barred by the freeze. The owner's ruling then applies in full. Urgent coordination issues in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate are filed BEFORE the fix merges, naming the old and new value: in the interrupted case `FLOW_FINISH_GATE_EXIT=0` becomes the real status (143 for SIGTERM, 130 for SIGINT). The marker's name and shape do not change, and its value for a run that was not interrupted does not change.


## Constraint
Freeze (#1673): fixes only, no new feature under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/`. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is by default; a change to one needs a coordination issue in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before the PR merges.

Parent: #1690 (child of #1673)


<!-- end of body -->
