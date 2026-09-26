# Issue #1258 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1258
- Read at:      2026-09-26T15:14:52Z
- updatedAt:    2026-09-26T14:12:31Z   (context only - moves on comments and labels)
- Body digest:  4daadb8095c547350bd976812c7ab82e3acba734a8f67928d3572e3c74cef9b8   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5774 of 5774 (cap 16384)

## Body as read
**Wave W1A**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S1**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S1** flow-start-resolve.sh creates a worktree on a merged-PR's issue branch before asking for confirmation (live; found during /flow:auto 982 kyle)
  - evidence: scripts/flow-start-resolve.sh:573-580 sets LANE=remote-pickup and calls create_worktree immediately after probe_pr_head; CONFIRM_REQUIRED is only a downstream flag, the worktree already exists by the time it's reported
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5812025056
- [ ] **S1** flow-start-resolve.sh picks up a merged-PR branch for an open issue before asking (restatement of idx320) (live; found during /flow:auto 982 (kyle))
  - evidence: Same code path and same /flow:auto 982 kyle repro as idx320; scripts/flow-start-resolve.sh:573-580 unchanged
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5818648859
- [ ] **S1** flow-start-resolve.sh's worktree path derivation fails when the repo sits at filesystem root, leaving a stray branch (live; found during /flow:auto 1275 (kyle), containerised session)
  - evidence: scripts/flow-start-resolve.sh wt_path_for() (L378-388) unchanged: `$(dirname "$TARGET_REPO")/...`; no writable-parent check or fallback base, and create_worktree still runs `git worktree add -b` before any writability check
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5833895717
- [ ] **S2** flow-start-resolve.sh derives COMPOSE_PROJECT_NAME from the checkout basename, wrong in a kyle container mounted at /workspace (live; found during /flow:auto 1275 (kyle))
  - evidence: scripts/flow-start-resolve.sh:635-636 unchanged: reads .claude/deploy.yaml override else `basename "$TARGET_REPO"`; no fallback to the compose file's own top-level `name:` field
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5833895904
- [ ] **S1** flow-finish-gate.sh's verdict() prints without exiting; only one call site is regression-tested (partially-delivered; found during #1147)
  - evidence: scripts/flow-finish-gate.sh:311 verdict() still only echoes; only test_a_runner_json_without_a_gate_set_fails_closed (tests/test_flow_finish_gate.py:~1718) asserts a single marker for that one input - no shared helper enforcing it across the ~93 FLOW_FINISH_GATE assertions in the file
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751756836
- [ ] **S1** check-ignored-additions.sh warns at exit 0 for a newly-staged file silently dropped by .gitignore (live; found during #1069 (PR #1144))
  - evidence: scripts/check-ignored-additions.sh exits 0 unconditionally when not --strict (only --strict exits 3); no distinction between a just-staged ignored path and pre-existing ignored clutter
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751056826
- [ ] **S2** flow-finish-gate typecheck ignores the target repo's declared mypy scope, falling back to mypy . (live; found during cooneycw/skillc#18 via /flow:auto)
  - evidence: lib/cicd/models.py:148,162 still hardcode `"typecheck": "uv run mypy ."` for both Python/uv and Django/uv runners, no [tool.mypy] files detection
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5833225805
- [ ] **S2** Finish gate typecheck hardcodes mypy ., ignoring a repository's declared mypy scope (precise line cite for idx339's defect) (live; found during cooneycw/skillc#5 (PR skillc#33), Step 6 finish gate)
  - evidence: lib/cicd/models.py:148 (also :162) confirmed hardcoded `uv run mypy .`, exactly as cited
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5846396753
- [ ] **S2** flow-finish-gate reports "1 failed" without naming the failing test, undiagnosable without a full rerun (partially-delivered; found during issue #1232 / PR #1238)
  - evidence: lib/cicd/runner.py:1211-1400 now captures failed pytest ids (`_failed_ids_from_both_streams`) and performs a targeted re-run (#769/#900/#804/#915/#1027 lineage) recording an `ids`/`reruns` block, but only when the count is <=MAX_RERUN_IDS(25) and ids can be parsed; the reported scenario (three subsequent green runs, test never identified) suggests this path can still fail to attribute
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5812196335
- [ ] **S4** flow-finish-gate.sh mktemp'd RUNNER_JSON has no EXIT trap, leaks on early exit (live; related 951; found during 951 (wayfinder map #950))
  - evidence: scripts/flow-finish-gate.sh:637 mktemp, cleanup only a straight-line `rm -f "$RUNNER_JSON"` at :909; the script's own EXIT trap at :137 only prints exit status, does not rm the temp file
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5677759954

## Negative control (ADR 0008)

Commit a case for each gate that makes it report the OTHER verdict: an issue whose branch has a merged PR must be refused BEFORE any worktree exists; a `fail` verdict followed by an `ok` must still exit nonzero; a staged file dropped by `.gitignore` must fail, not warn; a repo that declares a mypy scope must be typechecked on that scope and nothing else.

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
