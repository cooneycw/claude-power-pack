<!-- flow-run n=1 id=af476536136d4620ba2a4717ca6c955e -->
## Run 1 - issue #1557 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1557
- Read at:      2026-10-24T23:05:16Z
- updatedAt:    2026-10-24T22:55:19Z   (context only - moves on comments and labels)
- Body digest:  7084155e0068df6c70182c0cabae25fb969bef7a3d095747ddbdf93a5c8bdd79   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3699 of 3699 (cap 16384)

### Body as read
## Problem and concrete blocker

CPP PR #1556 (issue #1554) cannot pass required `ci/woodpecker/pr/woodpecker`: pipeline 3344 fails `counter-model-enrolment`. The production enrollment gate independently reproduces exit 1: `FLOW_FINISH_GATE_COUNTER_MODEL: missing: no receipt for branch ... at a commit reachable from HEAD`.

Two real independent `gpt-6-astra` reviews ran, with original report/stream hashes, model/thread IDs and measured scope/network/credentials preserved in `docs/flow-runs/issue-1554.md`. The current writer refuses the implementer thread because its entire original rollout contains early registration under `gpt-6-astra` and implementation under `gpt-6.1-sol`: `turn_context records disagree (gpt-6-astra, gpt-6.1-sol)`. A prose disposition was truthful but does not satisfy required CI; it is not bypass authority. Canonical previously recorded finding: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6389865902 .

This is now an in-scope delivery dependency for #1554, authorized by the `skillc-complete` orchestrator. Priority is truthful receipt repair, then PR #1556, then #1555. No implementation is approved by creating this issue: a fresh concrete Step3 ruling is required.

## Intended behavior and boundaries

Support truthful issue/run-scoped attribution from the original, unfiltered rollout when the full-thread model set includes unrelated earlier work. Bind scope to actual issue/run/approved-plan evidence and prove its start precedes all implementation for the task. Preserve the original rollout hash and explicitly account for excluded context. Do not accept a caller-chosen convenient model window that can omit implementation.

The default remains fail-closed: ambiguous threads and mixed models inside the actual implementation scope refuse. Do not filter or fabricate rollouts, manufacture a review/skip receipt, rename a completed review as skipped, weaken the independent-model property, or bypass/relax enrollment/required CI. Existing two completed reviews stay real evidence; any receipt must be re-derivable from their original streams and the original implementer evidence.

## Acceptance

- Establish a minimal bounded attribution contract and the actual #1554 boundary evidence before code; demonstrate why it predates every implementation edit, rather than beginning near receipt creation.
- Commit positive and negative controls for missing, malformed, conflicting or overlapping bounds; actual mixed models inside implementation; ambiguous default behavior; and attempts to choose a narrower convenient model window.
- Demonstrate regressions red on the old helper and green after the fix through production entry points. Retain all existing attribution/enrollment controls.
- Record original full-rollout digest, scope binding, excluded-context facts and reviewer evidence without publishing private raw rollouts or host paths.
- Obtain a truthful #1554 receipt from the repaired helper, commit it, rerun the unchanged enrollment gate, and obtain full exact-head required CI for PR #1556 before merge.
- Run appropriate tests, full quality gates and counter-model review for the helper change; no paid trial, deployment, host configuration or broad provenance platform.

The wider state-byte producer dependency #1555 and the frozen skillc #557 study are separate and must remain unchanged by this repair.

Also blocks cooneycw/skillc#536 PR A: the worker reports full make verify exit 0 (6,977 passed, 5 skipped), followed by outer flow-finish enrollment exit 1 for the same mixed-thread/missing-receipt limitation. Both deliveries remain held for merge; truthful draft PR preparation is permitted, bypass is not.


<!-- end of body -->
