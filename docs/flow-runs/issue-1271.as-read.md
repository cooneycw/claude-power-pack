# Issue #1271 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1271
- Read at:      2026-09-27T13:29:13Z
- updatedAt:    2026-09-26T14:12:45Z   (context only - moves on comments and labels)
- Body digest:  f321346e5efbc24516b8f14f35f8ac3968bc8729bdefcfc67ba5267e882fa53d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 7360 of 7360 (cap 16384)

## Body as read
**Wave W3F**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S3**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S3** test_flow_wave_mailbox.py leaks __supervise_daemon processes that outlive the run and pin worktrees open (unverified; found during sweeping worktrees after #1027)
  - evidence: reported 4 leaked daemons on host, one reparented to systemd --user; not re-run here (read-only task)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5742812306
- [ ] **S3** Interrupted pytest run leaks a self-re-arming supervise daemon with no cross-run reaper (live; found during orchestrating claude-improvements wave)
  - evidence: tests/supervise_reap.py's _UNREAPED set (:265) is a module-level/per-process-lifetime tracker; no sweep exists that scans for __supervise_daemon processes whose pytest tmpdir no longer belongs to a live run
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5766401516
- [ ] **S3** Seven older mailbox tests inherit host session lineage and fail outside Claude Code (fixture leakage since #1237) (live; found during post-#1228/#1237 implementation assessment)
  - evidence: Root cause confirmed unchanged (same watch_state_of fallback verified for idx318); no pinning of FLOW_WAVE_SESSION_PIDS/FLOW_WAVE_SOCK_DIR found in the named older test helpers; could not re-run the suite to directly reconfirm the 7 failures
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5818464125
- [ ] **S3** test_the_repo_wide_scan_is_clean_with_the_fixture_committed asserts over the whole working tree, not the tracked repo (live; found during CI wall-clock measurement (pytest-parallelism investigation))
  - evidence: tests/test_secret_scan.py: `_scan(ROOT, CONFIG)` passes `--no-git`, asserts `_findings(result)==0` over every file on disk including gitignored local files
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743285044
- [ ] **S3** test_flow_wave_registry.py may share test_flow_wave_mailbox.py's host-ps-scan false-red coupling - never checked (unverified; related #1092; found during #1092 / PR #1105 clean-stop checklist)
  - evidence: author explicitly flags this as unchecked; a targeted scan of tests/test_flow_wave_registry.py found no obvious host-wide `ps`-scan assertion pattern, but this is not conclusive against the specific hazard described
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5745059390
- [ ] **S3** Mailbox supervise shutdown-timing test failed once under parallel load, passed on rerun (unverified; related 1114; found during #1114 / PR #1123)
  - evidence: single observed rerun-pass event 2026-09-20 during flow-finish-gate; not independently reproduced here (no test execution performed, read-only task)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749981342
- [ ] **S3** checkout-readers positive control disagreed between JSON payload and human report under parallel load, once (unverified; found during issue #1189 / PR #1233, Step-7 re-gate)
  - evidence: Requires running the full parallel suite to confirm reproduction; task scope forbids running make/pytest
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5811996103
- [ ] **S3** Real-tree negative-control battery readers don't take the live-tree lock and now share one sample since #1241 (unverified; found during issue #1241 / PR #1250)
  - evidence: Author's own text flags this as unmeasured/speculative; requires running the suite with a planted probe to confirm, which is out of scope here
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5819371782
- [ ] **S3** control_block() keys on gate name, which is no longer unique once a gate registers 2+ controls (live; related 1117; found during #1117 / PR #1125)
  - evidence: tests/test_negative_controls.py:111-119 control_block matches first NEGATIVE_CONTROL_GATE: line; latent per author (no gate has 2 registrations via this path yet)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749985832
- [ ] **S3** test_verify_coverage_check.py asserts a substring where it means a target-name token (live; found during #1168)
  - evidence: tests/test_verify_coverage_check.py:606/:638 still use `"make negative-controls" not in result.stdout` (substring), not a word-boundary/line match
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5752555006
- [ ] **S3** test_flow_wave_mailbox.py timeout oscillated 60->10->20 with no reversal-trigger note (live; related 936; found during 936 / PR #1000)
  - evidence: tests/test_flow_wave_mailbox.py has multiple timeout=20 sites (e.g. :1976, :2149, :3298 etc.) with no comment stating what would move it back; disposition was deliberately not to fix (another worker's lane)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5684521856
- [ ] **S4** test_detector_contracts.py probe dir collides across concurrent same-worktree pytest runs (live; found during 834)
  - evidence: tests/test_detector_contracts.py:181-182 probe.parent.mkdir(..., exist_ok=False) against fixed path, no pid suffix. Orchestrator ruled not worth changing on PR #879.
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5648617053
- [ ] **S3** test_eli5_gate_not_bypassable.py covers 3 of 6 relevant driver surfaces, name implies full coverage (live; related 965; found during 953, confirmed while building 965's tripwire)
  - evidence: tests/test_eli5_gate_not_bypassable.py:47 GATE_SURFACES = ("eli5.md", "auto.md", "help.md") - auto_codex.md dropped (retired #1017) but codex/auto.md, qwen/auto.md, gemma/auto.md still not reached by this test
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5678900901
- [ ] **S3** flow-live-driver-guard.sh defaults WORKTREE_PATH to ambient cwd, can report clear about the wrong repo (live; found during codex-power-pack #246)
  - evidence: ~/.claude/scripts/flow-live-driver-guard.sh:28 'default: current directory' unchanged; no requirement or git-toplevel validation added
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5680150920
- [ ] **S3** flow-stale-check.sh:180 fail-open '|| echo 0' defused only by an unrelated guard 7 lines above, no committed dependency (live; found during codex-completion wave, worker-E scan)
  - evidence: scripts/flow-stale-check.sh:176-183 - base-ref existence check at :176-178 uses `verdict unknown`, but `behind=$(git_ rev-list --count "HEAD..${BASE_REF}" 2>/dev/null || echo 0)` at :183 still falls back to 0/'current' rather than 'unknown' on its own
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5679026336

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
