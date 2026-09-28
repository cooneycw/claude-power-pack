# Issue #1297 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1297
- Read at:      2026-09-28T11:54:55Z
- updatedAt:    2026-09-27T17:59:07Z   (context only - moves on comments and labels)
- Body digest:  31a85a729d689386db1bf3ddf659ea04ef051ddf964ee8c96fe1c2d914e1ac12   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2573 of 2573 (cap 16384)

## Body as read
## Outcome

The supervise identity-escalation regression test establishes that its child is ignoring SIGTERM before the sweep starts, so CI failures reflect a broken identity check rather than fixture startup scheduling.

Derivative of #1271 / PR #1295, discovered while merging #1294 / PR #1296. Existing report: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5858191432. Prioritized by the owner's request to review the merging sessions and plan follow-up flow:auto work (#1292).

## Evidence and uncertainty

The existing report records `tests/test_supervise_sweep.py::test_identity_is_rechecked_before_the_kill_escalation` failing with `assert 1 == 2` in Woodpecker PR pipeline 2769, while push pipeline 2768 passed on the same SHA `c9fc698`. These CI observations are the original reporter's evidence; this coordination review has not independently rerun those historical pipelines.

Verified on main `ce5f296`: `_fake_daemon` waits for the expected argv in `/proc/<pid>/cmdline`, then returns. The target test's shell installs `trap '' TERM` only after exec. Seeing argv does not establish that the trap has run. The proposed race explanation is consistent with that source but has not yet been reproduced as the historical failure's cause.

## Acceptance

- Reproduce the readiness gap with a controlled delayed child startup; show how the pre-fix fixture can signal before the trap is installed. Keep the test scoped to its own child/process group and clean it up on all outcomes.
- Establish bounded, explicit readiness after the trap is installed. A child that exits early or never becomes ready must fail clearly with cleanup; do not fix the race by lengthening an arbitrary sleep, skipping the assertion, or retrying until green.
- Keep the actual safety negative control: a changed identity during TERM grace prevents SIGKILL to the replacement process. The fixed fixture must still expose a deliberately broken escalation identity check.
- Run the focused suite through make, then normal flow verification and the required PR CI lane. State separately which observations were reproduced and which were inferred.
- Reconcile #1271's delivered/dispositioned obligations with this derivative; don't redo its already-merged implementation or close it solely because PR #1295 merged.

Scope: fixture readiness and its tests, plus necessary run records. Change production reaper logic only if a separate reproduced defect requires it and the plan is revised. Proposed first follow-up for projects-88; no worker acknowledgement recorded yet.

