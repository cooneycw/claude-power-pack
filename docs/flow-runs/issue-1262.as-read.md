# Issue #1262 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1262
- Read at:      2026-09-28T10:43:32Z
- updatedAt:    2026-09-26T14:12:36Z   (context only - moves on comments and labels)
- Body digest:  3f4373107f2e5a91a2a7925f0c71e49dd7b31e912713a7573d598d6abc1ebc74   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6447 of 6447 (cap 16384)

## Body as read
**Wave W2A**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S2**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S2** flow-ci-status.sh defaults PREFER_EVENT=push, but only the pr lane is a required check on this repo (live; related 975; found during 975 / PR #1050)
  - evidence: scripts/flow-ci-status.sh:72 `PREFER_EVENT="push"` unchanged; `gh api .../branches/main/protection` required_contexts still only ["ci/woodpecker/pr/woodpecker"]
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740692347
- [ ] **S2** flow-ci-status.sh resolves repository identity from caller cwd rather than declared --path (unverified; found during cooneycw/codex-power-pack CxPP #286 / PR #288)
  - evidence: reported via scripts/flow-ci-status.sh:151-158 (gh repo view runs in caller cwd; sed fallback keeps optional .git suffix); found while working a different repo, not independently reproduced here
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5742151455
- [ ] **S2** flow-ci-status.sh --wait reports an expired wait identically to an unregistered push, both exit 0 (live; found during kyle #1233 PR-A merge, wave kyle-improvements, worker-D)
  - evidence: scripts/flow-ci-status.sh:248-255 the --wait loop breaks on deadline with STATUS still 'not-found'; no distinct 'never-created'/FLOW_CI_WAIT_EXPIRED verdict or non-zero exit for that case
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5766223769
- [ ] **S2** gh-pr-merge.sh completeness check false-positives on PRs over 100 files (unpaginated file list) (live; found during merging PR #1144 (#1069))
  - evidence: scripts/gh-pr-merge.sh:1490 `gh pr view ... --json files` with no --paginate; verify_completeness() (~line 1486-1512) reports 'violation' with no truncation/count check
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751119182
- [ ] **S2** Follow-up to idx=146: a THIRD condition behind BASE_STALE - the PR has already squash-merged, and the printed remedy loops against a closed PR (live; related 1026; found during 1026, merging PR #1053)
  - evidence: scripts/gh-pr-merge.sh still has no `gh pr view <N> --json state` check before emitting GH_PR_MERGE_BASE_STALE (:1249-1265); the later MERGED-state check (:1520) is a post-merge backstop, not a pre-check that would short-circuit a repeated gate cycle against an already-merged PR. Update comment in the same thread establishes the wrong-directory and squash causes are independent, not one phenomenon.
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740834327
- [ ] **S2** GitHub PR state (mergeStateStatus=BEHIND + green) cannot distinguish an abandoned PR from one mid-finish; only a /proc scan can, and it's not in the merge path (live; related 1017; found during cpp-issues wave, shepherding PR #1038)
  - evidence: No comparison of local worktree HEAD-ahead-of-PR-head exists in scripts/gh-pr-merge.sh or flow-pr-watch.sh; the /proc cwd scan documented elsewhere is not invoked by any merge predicate
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740510212
- [ ] **S2** flow-pr-watch admits a control's own complete pytest summary as an authoritative run (live; found during post-#1214/#1190 implementation assessment)
  - evidence: Residual case extending an earlier comment (5765261081); author's own repro at CPP main 3997e519 measured false-red/count-contamination via existing test harness; did not demonstrate false-green or remeasure a live pipeline
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5799203158
- [ ] **S2** ELI5 Section B only prescribes remote-facing staleness checks, misses local unpushed sibling worktrees (live; related 597; found during /flow:auto 1127 Step 2/3)
  - evidence: .claude/commands/flow/eli5.md Section B (~line 94-122) still only prescribes git log --since / gh pr list / gh issue list; no git worktree list
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750258624
- [ ] **S3** gh-pr-merge.sh's BASE_STALE guard reads HEAD of whatever cwd it's invoked from and names neither the directory nor which HEAD it compared (live; found during cpp-issues wave, merging PR #1050/#1051)
  - evidence: scripts/gh-pr-merge.sh:1224-1260 still uses `BASE_WAIT_ROOT=$(git rev-parse --show-toplevel)` / local HEAD with no directory/HEAD naming in the 'does not contain' message
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740721709
- [ ] **S3** gh pr merge --delete-branch reports failure after a successful merge in worktree-per-issue layouts (unverified; found during #1094 (PR #1102))
  - evidence: gh CLI/environment behavior (main checked out in a sibling worktree); no CPP code to check; workaround already known (drop --delete-branch, delete remote branch separately)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5745069439
- [ ] **S3** 65 of 70 remote branches orphaned; gh pr merge --delete-branch silently skips deletion on a post-merge gh error (live; found during wave cpp-completion, merging PR #967)
  - evidence: scripts/gh-pr-merge.sh has no unconditional/separate branch-deletion step; no companion to flow-worktree-sweep.sh for remote branches. Denominator corrected by idx=62.
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5678253709
- [ ] **S3** worktree-remove.sh's landed-record check silently depends on gh-pr-merge.sh as the only writer (live; found during close of claude-improvements wave)
  - evidence: scripts/gh-pr-merge.sh:1532 writes branch.<b>.cpp-merged-head; scripts/worktree-remove.sh:601/667 reads it and refuses citing 'commits on no remote' with no mention of the merge-helper coupling
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5769067812

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
