# Flow run record - issue #1271

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1271
- Base SHA:          879df151d3a34b87f5df5c2f0b6606412ddc657b
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the session user (cooneycw), in-conversation "approved"
- Recorded at:       2026-09-27T14:05:00Z

## Section B evidence

- Commits since filing touching the lane's files: 4deccd2 (#1284), bdd2d14 (#1283), 7e68b47 (#1280).
- Merged PRs inspected: #1270, #1274, #1275, #1279, #1280, #1283, #1284, #1286, #1287.
- Related issues: #1116 (delivered item 1, commit 82ac508 / PR #1119), #1253 (delivered item 3, PR #1254), #1092, #1260, #1228.
- Item 1 delivered (0 leaked daemons after 7 mailbox+registry runs). Item 3 delivered in the mailbox file, but the same leak reproduced 2/2 in tests/test_flow_wave_registry.py TestWatchColumn (armed, stale) with FLOW_WAVE_SESSION_PIDS empty.
- Item 5 not reproduced: planted short-path neighbour watcher, registry file 253 passed.
- Item 6 reproduced 1 of 4 CI-like `-n 4` runs; 3/3 serial, 4/4 under CPU hog.
- Item 8 not reproducible: probe planted, battery reported TRACKING: UNTRACKED, all four readers passed.

## Section C - the approved plan

1. `tests/supervise_reap.py` - cross-run sweep of orphaned supervise daemons keyed on an owner marker whose pytest process is gone.
2. `tests/conftest.py` - export CPP_PYTEST_OWNER, sweep at session start (controller only), report in terminal summary.
3. `tests/test_supervise_sweep.py` - controls: dead owner reaped; live owner, no marker, non-daemon argv spared.
4. `tests/test_flow_wave_registry.py` - pin session lineage in the two TestWatchColumn positive controls.
5. `tests/test_flow_wave_mailbox.py` - wait on the inner watch child instead of sleep(1); SURFACE_WAIT constant with a reversal trigger.
6. `tests/test_checkout_readers.py` - victim lives until killed, process-group teardown, assert victim alive after scans.
7. `tests/test_secret_scan.py` - scan a copy of the tracked file set.
8. `tests/test_negative_controls.py` - control_block refuses an ambiguous gate; synthetic-output test.
9. `tests/test_verify_coverage_check.py` - make-target token matcher plus its test.
10. `tests/test_detector_contracts.py` - per-process unique probe dir.
11. `tests/test_eli5_gate_not_bypassable.py` - all six gate surfaces plus a tripwire deriving every */auto.md.
12. `scripts/flow-live-driver-guard.sh` - FLOW_LIVE_DRIVER_PATH line and a NOTE when the path was defaulted.
13. `tests/test_flow_live_driver_guard.py` - tests for the path line and note.
14. `.claude/commands/flow/auto.md` - Step 4 passes WT_PATH to the live-driver guard (plus regenerated codex/skills mirrors).
15. `scripts/flow-stale-check.sh` - failed rev-list reports unknown, not current.
16. `tests/test_flow_stale_check.py` - red case via a FLOW_STALE_GIT wrapper failing rev-list.
17. `docs/flow-runs/issue-1271.md` - this record (plus the counter-model receipt).

Scope: ~17 files plus mirrors, ~500-700 lines, mostly tests.
Risks: the sweep kills processes (mitigated by a three-part predicate and spared-case controls); item 6's mechanism is inferred, not captured; auto.md edit regenerates Codex mirrors.
