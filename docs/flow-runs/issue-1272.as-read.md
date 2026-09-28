# Issue #1272 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1272
- Read at:      2026-09-28T17:04:50Z
- updatedAt:    2026-09-26T14:12:46Z   (context only - moves on comments and labels)
- Body digest:  98caba7e949dcf84c60965e108c64e6414a0396eb3c6232ac0b5c2e2a401540d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 8546 of 8546 (cap 16384)

## Body as read
**Wave W3G**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S3**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S3** Nit-store repo->issue-number mapping duplicated verbatim in two command docs (live; related 878; found during 865)
  - evidence: .claude/commands/flow/finish.md:440 and .claude/commands/codex/code_review.md:313 both hardcode identical case-statement mapping
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5648626071
- [ ] **S3** No retirement/staleness rule exists for shipped .specify/specs/ spec files (live; found during owner-requested SDD research, no issue/PR)
  - evidence: grep -iE 'after (the )?(work )?(ship|merge)|once (shipped|merged)|spec.*(stale|supersed|archiv|delete)' docs/agents/issue-contract.md still returns no match; .claude/commands/spec/help.md workflow list still stops at /flow:auto
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5662672201
- [ ] **S3** #934 acceptance criterion requires binding to a 'tier' signal that has no machine-readable form anywhere (live; related 934; found during 934 Step 3, cpp-completion wave)
  - evidence: `gh label list` still shows only tier-4 (a stray), no tier-1/2/3; 'tier' still only prose in evaluate/issue.md and spec/help.md
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5684886802
- [ ] **S3** README install section presents already-delivered #663 installer as future work; v8 release unverifiable (live; related #1037; found during owner-requested longitudinal repository assessment)
  - evidence: README.md:32,38 still read "issue #663 restores..." / "restored canonical installer lands in issue #663"; #663 closed 2026-08-11
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741511028
- [ ] **S3** docs/scripts.md still documents pre-#1058 occupied-but-clean worktree-remove behavior, now inverted (live; related #1032, #1058; found during #1032 (specimens #2/#3))
  - evidence: docs/scripts.md:211 "Occupied AND dirty is a hard stop"/"Occupied-but-clean still removes" vs scripts/worktree-remove.sh:18-20 "whether the tree is currently dirty or clean" (both refused since #1058)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743382998
- [ ] **S3** shared-stash-stack.md doesn't warn other destructive git commands are riskier in CPP's shared-worktree layout (live; related #1056, #1092; found during #1092 / PR #1105 near-loss incident)
  - evidence: docs/agents/shared-stash-stack.md (175 lines, checked in full) documents the stash hazard and its `push`-only enforcement limits but has no corollary about `git checkout --`/`git reset --hard` or a backup-patch alternative
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5745058813
- [ ] **S3** Stale gpt-5.5 attributions remain in 6 test/README/CHANGELOG prose sites (live; related 1048; found during #1048 / PR #1112)
  - evidence: tests/fixtures/counter_model/README.md:5, tests/test_flow_driver_retirement.py:446, test_flow_wave_registry.py:3802, test_negative_fixture_preconditions.py:544, test_lane_serveability.py:1233, CHANGELOG.md:883 all still say gpt-5.5
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749164928
- [ ] **S3** README still advertises retired dockerfile-lint CI step in 3 places (live; related 943; found during #962 / PR #1118)
  - evidence: README.md:17,99,143 still mention Dockerfile lint; step removed by #943
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749661967
- [ ] **S3** README control-count prose stale (says 6/63, actual is far higher and drifting further) (live; related 1028; found during #1028)
  - evidence: README.md:215-216 still "six registered controls...63 enumerated"; measured now 54 controls in controls/, 107 census rows
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749670973
- [ ] **S3** Secrets-UI remediation string tells operator to install nonexistent 'creds' PyPI package (live; related 1041; found during #1041 / PR #1122)
  - evidence: lib/creds/ui/app.py:40, .claude/commands/secrets/ui.md:24, codex/skills/secrets-ui/SKILL.md:30 all still print uv pip install 'creds[ui]'; pyproject.toml now has a real ui extra (#1041) so `uv sync --extra ui` would be correct but unused
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749867253
- [ ] **S3** #992's 'unguarded shift 2 spins forever' claim is bash-specific, false for POSIX sh gates (live; related 992; found during #1126)
  - evidence: docs/scripts.md gate-lib section + tests/test_gate_lib.py pin the sh-vs-bash distinction; no correction note added to #992's own closed body (not verified)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750282749
- [ ] **S3** drift-check's verify-coverage annotation falsely claims it repairs and writes to HOME (live; related 1028; found during #1139)
  - evidence: Makefile:800 still reads '... REPAIRS them; it inspects and writes to HOME' while scripts/drift-detect.sh's fix() only echoes remediation text (no cp/ln/mkdir/tee/rm executed)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750882113
- [ ] **S3** register.md's crossSessionInbound claim ('neither end can measure it alone') is contradicted by observed harness notices (live; found during /flow:register worker-E into kyle-improvements)
  - evidence: .claude/commands/flow/register.md:~974-981 still reads '...neither end can measure it alone... Do not attempt it in that shape'; the line-673 row still cites bare `success=true` as its basis, unrevised
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5775490763
- [ ] **S3** Two fleet records disagree on the crossSessionInbound hold cause, neither cross-references the other (live; found during /flow:register worker-CC into kyle-improvements, 2026-09-23)
  - evidence: register.md's contested block (idx=292, still unrevised on main) and the separate memory file held-message-is-queued-not-failed.md give competing causes with no cross-reference; unreconciled as of main 85e9b03
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5794116236
- [ ] **S3** cpp:init describes the Trusted profile as protected by safety hooks that don't exist (live; found during issue #1206 run 3 / PR #1230)
  - evidence: .claude/commands/cpp/init.md:209 unchanged: "Broad auto-approvals, rely on hooks for safety"
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5803585971
- [ ] **S3** flow:doctor repeats the retired claim that scripts/hooks provide security protection (live; found during codex counter-model review of PR #1230 (#1206 run 3))
  - evidence: .claude/commands/flow/doctor.md:440 unchanged: "Scripts and hooks are ... since they provide security protection"
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5803586165
- [ ] **S3** docs/scripts.md still states the gemma host is pinned, contradicting a later owner ruling that it is unpinned (partially-delivered; found during issue #921 half 2 / PR #1234)
  - evidence: docs/scripts.md:471 still states as fact `OLLAMA_KEEP_ALIVE=-1`/19GB pin; :473 (added by PR #1234) now notes the owner ruling supersedes it as a planning assumption, but line 471 itself was not rewritten, matching the reporter's own note
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5811687786
- [ ] **S3** flow/register.md contradicts itself on file-lane overlap semantics (containment vs exact-match) (live; found during cooneycw/kyle#1296, wave kyle-solidify, worker-C)
  - evidence: .claude/commands/flow/register.md:251 ("A declared directory contains the paths under it") still contradicts :1299 ("File-lane overlap is EXACT-MATCH on declared paths")
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5846311281

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
