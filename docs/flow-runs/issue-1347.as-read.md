<!-- flow-run n=1 id=a342cf208c904ba4b064bf8beb5e179d -->
## Run 1 - issue #1347 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1347
- Read at:      2026-09-28T22:25:18Z
- updatedAt:    2026-09-28T22:23:46Z   (context only - moves on comments and labels)
- Body digest:  a3ac994684ab5a50914bafce455627531469189dce46457cbf60f85df5778a73   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2272 of 2272 (cap 16384)

### Body as read
Regression introduced by PR #1344 (846431d, #1343). The test added to stop the orphaned `sleep 300` is flaky under the parallel suite, and when it fails it leaks the orphan it exists to prevent.

**Observed** (the full record is at https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5879817971): under `make -k verify` (`pytest -n 4`), on 846431d plus unrelated #1341 commits, in a Kyle container where every process runs as the same uid:
- `test_cleanup_of_a_shared_group_fixture_leaves_no_descendant[one-child]` failed with `could not read pid 502737's environment: [Errno 13] Permission denied`. It was the only failure in 7007.
- Run alone, it passes on both the branch and main.
- After the suite, the fixture's `__supervise_daemon` bash and its `sleep 300` were left running with ppid 1.

**Two defects:**
1. `_kin` (`tests/test_supervise_sweep.py`) turns EACCES on ANY same-uid pid into `pytest.fail`. A same-uid process can be legitimately unreadable for a moment, for example a non-dumpable process or one mid-exec belonging to another xdist worker. So a neighbour's process fails this test. The "unreadable of ours is unobserved, not absent" rule was right in intent, but its population is wrong: it should apply to pids that could be in the fixture's tree, not to every process of the uid.
2. The precondition loop (`while not [pid for pid in _kin(tag) ...]`, ~L440) and the assertion both call `_kin` outside any `try/finally`. Any raise in it skips `_cleanup(proc)`, so the failure path leaks the fixture.

**Outcome:** the test fails only on a real survivor or on an unreadable process that could be the fixture's. A failure never leaks the fixture. `ps` after the suite is clean whether the test passes or fails.

**Acceptance:** a committed case where a same-uid, unrelated, unreadable pid does NOT fail the check. The existing `test_an_unreadable_process_of_ours_fails_the_cleanup_check` other-verdict case still reds for a candidate that could be ours. A case that forces `_kin` to raise mid-test and asserts the fixture is still reaped.

It is not expected to red CI, which runs as root, where root reads every environ. It reds local and container full-suite runs, and on every failure it leaves the #1343 orphan behind. Refs #1343.

