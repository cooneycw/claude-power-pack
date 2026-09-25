# Issue #1253 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1253
- Read at:      2026-09-25T14:21:25Z
- updatedAt:    2026-09-25T14:17:29Z   (context only - moves on comments and labels)
- Body digest:  b52d46b300fdb9b7c4bc19d81cf174b6d78ac5b2831369727eefb51965938443   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4722 of 4722 (cap 16384)

## Body as read
## Outcome

Make the seven watcher-state tests in `tests/test_flow_wave_mailbox.py` independent of the launching agent and host session sockets, so local verification and CI exercise the same intended conditions. Preserve production `no-wake` detection.

Promoted from the [Sep 24 Nit Store finding](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5818464125), with repeat evidence from Sep 25. This is a test-isolation defect; the seven failures do not establish seven production mailbox defects.

## Verified evidence

- At `693c4773c885ac9d3224e8f74d70f45d71f15fab`, local `make verify` exited 2: **7 failed, 5913 passed, 2 skipped**.
- At `39c8475a937846ccfb29d7608037c841d0fab2a8`, local `make verify` again exited 2: **7 failed, 5959 passed, 2 skipped**. The [same revision's CI pipeline 2706](https://woodpecker.essent-ai.com/repos/1/pipeline/2706/1) succeeded.
- All seven failures expect `armed` or `stale` but receive `no-wake`:

```text
TestListWatchState::test_list_reports_armed_while_a_watcher_is_live
TestListWatchState::test_stale_needs_a_live_watcher_that_stopped_refreshing
TestListWatchState::test_stale_threshold_is_configurable
TestListWatchState::test_a_role_that_armed_before_any_box_exists_is_still_reported
TestWatcherIdentityAcrossDirectories::test_a_live_watcher_in_a_different_directory_is_not_counted
TestWatchStatus::test_status_reports_rearmed_yes_while_a_watcher_is_live
TestWatchStatus::test_one_watcher_counts_once_despite_its_own_subshells
```

The older `_live_watcher()`, `_run()`, and `_run_at()` helpers inherit the environment without establishing the session lineage their assertions assume. In `scripts/flow-wave-mailbox.sh`, `is_session_pid()` and `session_ancestor_of()` use `FLOW_WAVE_SESSION_PIDS` or the session socket directory; `watch_state_of()` correctly distinguishes a confirmed orphan from a session-owned watcher. Newer `TestWakeability` cases already use the explicit PID seam.

A controlled probe of the first test, without source changes, produced:

| Lineage environment | Result |
| --- | --- |
| Native review environment | FAIL: `no-wake` versus `armed` |
| `FLOW_WAVE_SESSION_PIDS` explicitly empty | Same FAIL |
| `FLOW_WAVE_SESSION_PIDS` names the Python process launching pytest | PASS |
| PID override unset; `FLOW_WAVE_SOCK_DIR` points to a nonexistent temporary directory | PASS through unknown-lineage fallback |

The four-arm probe was run on one representative test; the full verification run establishes the seven-test failure set. A declared test PID is fixture evidence, not proof of real agent notification.

## Reproduction

At the Sep 25 revision, with test dependencies installed:

```sh
FLOW_WAVE_SESSION_PIDS='' .venv/bin/python -m pytest -n0 -q tests/test_flow_wave_mailbox.py::TestListWatchState::test_list_reports_armed_while_a_watcher_is_live
```

Run `make verify` in the ordinary developer environment to check the complete failure set. The deterministic command above explicitly declares no session; the defect is that the fixture assumes session ownership without creating it.

Local scan artifacts: `/home/cooneycw/Downloads/cpp-final-scan-evidence-2026-09-25/` (`verify.log`, `lineage-probe.py`, `lineage-probes.json`). The essentials are reproduced here so acceptance does not depend on those local files.

## Proposed approach (revisable)

Give the affected watcher-state fixtures explicit, fixture-owned lineage using the existing test seam and controlled socket paths. Keep intentional orphan and unknown-lineage tests independent. Verify process lifetime and cleanup under the normal parallel test configuration.

## Acceptance and boundaries

- All seven tests pass individually and in the full suite regardless of inherited PID override or presence of host session sockets.
- Positive session-owned, confirmed-orphan (`no-wake`), and unavailable-lineage cases remain separately covered; no suite-wide fake-session override masks negative controls.
- Demonstrate failure before the fix and success afterward using controlled lineage environments, including the reproduction above.
- Run `make verify` in ordinary developer and CI-equivalent environments; report actual counts and any unrelated failures.
- Fixtures do not require a live Claude session or modify user runtime sockets; watcher subprocesses are cleaned up.
- Do not skip/weaken assertions or relax production `no-wake` semantics to obtain green tests. No transport rewrite or Kyle integration is required.

The broader question of how unknown lineage is presented is [already recorded separately](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5811737647) and is outside this fix. Related production change: #1228.

