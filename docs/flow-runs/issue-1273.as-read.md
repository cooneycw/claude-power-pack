# Issue #1273 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1273
- Read at:      2026-09-28T17:28:14Z
- updatedAt:    2026-09-26T14:12:47Z   (context only - moves on comments and labels)
- Body digest:  8c288798df5b8eae57358f9afae2c3592becb98d4192a13952abfad7a453d539   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 13968 of 13968 (cap 16384)

## Body as read
**Wave W4**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S3**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S4** Duplicated sentence in acceptance-accounting rule, mirrored across 4 files (live; related 874; found during 861)
  - evidence: .claude/commands/flow/finish.md:295-296, flow/auto.md:837-838, codex/skills/flow-finish/reference.md:297-298, flow-auto/reference.md:839-840 all still repeat the clause
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5647308210
- [ ] **S4** class-enumeration-2026-09-15.md:188 still misclassifies #961 as 'absent' after the real fix (#1044) proved it 'dormant' (live; related 1044; found during 961 / PR #1043)
  - evidence: docs/research/class-enumeration-2026-09-15.md:188 still reads '#960 shellcheck, #961 pip-audit, #962 bandit fail clause 1 (exists)'; the underlying code defect was separately fixed and closed as issue #1044 ('lib/security's pip-audit adapter...'), confirmed CLOSED via gh issue view, but the research doc's sentence about it was never corrected
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5705334930
- [ ] **S4** Triage note: #1028/#1047 issue bodies overstate what's undelivered vs current main (live; related #1028, #1047, #1048; found during owner-requested open-issue progression assessment)
  - evidence: Makefile:392 codex-skills-check now an explicit `verify` prerequisite (stronger than the transitive-test coverage the nit cites); scripts/counter-model-receipt.py:445 validate() still rejects equal reviewer/implementer
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741516436
- [ ] **S4** Issue #918 deleted from GitHub; still cited as a live reference in dependency-advisory doc (live; found during #943 / PR #1064)
  - evidence: docs/security/dependency-advisory-dispositions.md:237 cites "#918's fastmcp bound"; `gh issue view 918` returns not-found
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5742141673
- [ ] **S4** code_review.md ships a stale dated inline model-name example readers may copy (live; related #1045; found during #1054 counter-model receipt writing)
  - evidence: .claude/commands/codex/code_review.md:16-17 still names a specific dated model ("gpt-5.6-sol"); same defect class as #1045's prior fix, one iteration later
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743118375
- [ ] **S4** README still advertises a Dockerfile-lint/hadolint CI step retired by #943 (live; related #943, #469; found during #1086)
  - evidence: README.md:17,99,143,219 mention Dockerfile lint/hadolint; .woodpecker.yml has no hadolint step (retirement documented in its own header comments)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743552960
- [ ] **S4** Unicode em dashes remain in bash-prep.sh and test_runner.py, outside check-unicode-dashes.py's tracked-.md-only scope (live; related #1037; found during #1037)
  - evidence: scripts/bash-prep.sh has 10 em dashes, tests/test_runner.py has 1; scripts/check-unicode-dashes.py confirmed scoped to `git ls-files *.md` only - a documented, deliberate scoping decision
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5744592387
- [ ] **S4** /self-improvement:retro references nonexistent /second-opinion:grill-plan command (live; found during cooneycw/kyle#1284)
  - evidence: .claude/commands/self-improvement/retro.md:6,351 still cite grill-plan; .claude/commands/second-opinion/ only has help.md, models.md, start.md
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750584037
- [ ] **S4** Makefile prose block for host-surface-check sits above the wrong target (live; found during #1146 (CI-disposition gate))
  - evidence: Makefile:674-679, the 'Host-surface declaration (issue #1139)' comment still sits directly above cpp-host-writes-check: rather than host-surface-check: eight lines below
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751621471
- [ ] **S4** The codex-power-pack Nit Store mapping still points at closed issue #227 in a private, dormant repo (live; found during issue #1236 / PR #1240)
  - evidence: grep confirms `codex-power-pack)  NIT_STORE=227 ;;` unchanged in .claude/commands/flow/auto.md:1311, flow/finish.md:441, codex/code_review.md:314
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5812203420
- [ ] **S4** Heredoc-guard test docstring falsely claims bash rejects an unterminated heredoc (live; related 914; found during 914)
  - evidence: tests/test_test_binary_guards.py:1447 still reads '...already broken and would not run' (measured false: bash warns and runs, exit 0)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5655429580
- [ ] **S4** Heredoc opener inside a quoted string can silently mask the rest of a script (undercount direction) (live; related 914; found during 914)
  - evidence: scripts/check-test-binary-guards.py:893,1557 `_mask_noncode(_mask_heredocs(text))` still runs heredoc-mask before quote-aware mask; author's own sweep found 0/93 in-tree instances (latent, not live)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5655430101
- [ ] **S4** forced-claim-check.py --selftest reports every file UNTRACKED when run outside a git repo, not 'unknown' (live; related 953; found during verifying merge of PR #968 (#953))
  - evidence: docs/research/forced-claim-prototype-2026-09-15/forced-claim-check.py:778-799 still runs `git ls-files --error-unmatch` directly with no prior `git rev-parse --is-inside-work-tree` probe
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5678649722
- [ ] **S4** scripts-inventory-check.py gives a different verdict locally vs CI when scripts/ holds an untracked file, undocumented (live; related 1013; found during PR #1024 / #1013)
  - evidence: scripts/scripts-inventory-check.py:213 still enumerates via `scripts_dir.iterdir()`; docs/scripts.md's scripts-inventory-check entry does not state EXAMINED includes untracked files (the specific documentation ask is unmet, though the iterdir choice itself is separately defended elsewhere in docs/scripts.md)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5704365754
- [ ] **S4** Accepted mutation-gap 'why' field is free prose, collapses into copy-pasted boilerplate across entries (live; related 1129; found during #1129 / PR #1135)
  - evidence: mutation-probe.py requires non-empty why for expect:uncaught but no enumerated blocked_by field; deliberately not widened in #1135
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750457062
- [ ] **S4** npm-global-upgrade.sh accepts empty --node value as a usage error masquerading as config (live; found during #1127 (PR #1149), recorded in tests/test_gate_migration.py ~line 379)
  - evidence: scripts/gate-lib.sh:238-256 gate_arg_value() deliberately decides on argc, not emptiness ('THE DECISION IS THE COUNT, NEVER THE EMPTINESS'); scripts/npm-global-upgrade.sh:108 --node still uses it unchanged
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751237408
- [ ] **S4** battery-in-ci-image proves each tool runs, then discards which version (live; found during #1165)
  - evidence: Makefile:583-587 battery-in-ci-image recipe pipes `--version` to /dev/null; no capture/echo of the tool version strings
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5752763435
- [ ] **S4** pytest parametrize id derived from parent.parent.name renders the checkout/worktree dirname, not portable (live; found during 958 / PR #1039)
  - evidence: tests/test_delivery_lane_versioned.py:758,785 still use `ids=lambda p: p.parent.parent.name + "/" + p.name` rather than a ROOT-relative path
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5705045540
- [ ] **S4** A well-argued negative-control fixture buys trust that stops anyone auditing its other blind axis (unverified; found during kyle #1235 / #1247 / #1239 triage)
  - evidence: meta/methodology finding spanning kyle #1235/#1247/#1239; no CPP code implicated, not independently re-checked here
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5744061637
- [ ] **S4** Test name/docstring overpromised 'registry sibling unavailable' when the fixture only breaks registry DATA, not the sibling script (partially-delivered; related #1095; found during #1095 / PR #1106)
  - evidence: tests/test_flow_wave_mailbox.py:2304-2318 test_registry_sibling_unavailable_fails_open_and_keeps_supervising - docstring reworded to a more neutral claim, but the test name is unchanged and the fixture (FLOW_WAVE_REGISTRY_DIR pointing at a missing dir) still never touches SUP_REGISTRY's script path (scripts/flow-wave-mailbox.sh:2830, resolved from $0's directory)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5745068631
- [ ] **S4** Index heading test needs hardcoded English number word per growth (partially-delivered; related 1109; found during #1109)
  - evidence: tests/test_detector_contracts.py count-word dict; #1109 branch added twenty-six but pattern remains
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5748930509
- [ ] **S4** make test runs the full negative-control battery twice for two single-line assertions (live; related 1117; found during #1117 / PR #1125)
  - evidence: tests/test_negative_controls.py two tests each call run_harness(ROOT) independently; author states explicitly "not a correctness defect"
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749985347
- [ ] **S4** requires_git skip reason falsely claims the CI validate image ships no git (live; found during issue #1242)
  - evidence: tests/test_host_surface_observe.py:600-602 unchanged: `reason="git absent (the CI validate image ships none)"`
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5812749116
- [ ] **S4** .gitignore ignores a .coverage artifact that nothing in the repo can produce (live; related 954; found during 954)
  - evidence: .gitignore:270 `.coverage` still present; no pytest-cov/coverage tooling in the repo
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5678087151
- [ ] **S4** gh pr diff <n> -- <path> silently returns empty instead of erroring; indistinguishable from 'no changes' (live; found during sequencing PRs during /flow:auto #1031 (PR #1087))
  - evidence: no shipped CPP code uses this form: `grep -rn "gh pr diff" scripts/ .claude/commands/ lib/` returns no matches; procedural hazard for ad-hoc queries only
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743597559
- [ ] **S4** Two correct measurements of a mutable Kyle release pointer were wrongly reconciled as a contradiction (unverified; found during cross-session Kyle current-prod deployment review)
  - evidence: process/reasoning finding about Kyle deployment state across two fleet sessions; no CPP code implicated, not independently checkable from this repo
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5744033831
- [ ] **S4** A finding held for a since-exited session's mailbox address is lost silently unless routed to the issue instead (unverified; found during fleet OOM-finding routing incident, kyle #1236)
  - evidence: fleet-process finding (mailbox vs issue routing rule); no code fix proposed or checkable here
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5744096102
- [ ] **S3** Shared nit-store resolver (3 call sites) never verifies its destination issue is open/correctly titled before posting (live; related #1030; found during #1030)
  - evidence: .claude/commands/flow/auto.md:1309-1318, finish.md:439-448, code_review.md:312-321 - identical hardcoded NIT_STORE map plus unchecked full-text-search fallback, unchanged in all three
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5744133769
- [ ] **S3** DeployConfig.from_dict destructively empties the caller's dict via data.pop (live; related 1113; found during #1113 / PR #1121)
  - evidence: lib/cicd/deploy/strategy.py:122-134 still uses data.pop for readiness/profiles/services/unknown keys, no dict(data) copy
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749791614
- [ ] **S4** Stale mypy exclude entry 'mcp-second-opinion' - directory retired by #469, never removed (live; related #469; found during #943 / PR #1064)
  - evidence: pyproject.toml:65 exclude list still names "mcp-second-opinion"; directory absent from tree
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5742140893
- [ ] **S3** bootstrap-agent-host.sh's docker-presence check gates installation of 4 unrelated packages (unverified; related #1029; found during cross-model review on PR for #1029)
  - evidence: woodpecker/bootstrap-agent-host.sh:37-43 unchanged: `if ! command -v docker` guards docker.io/docker-compose-v2/qemu-guest-agent/ca-certificates/curl install; original report was unverified on a real host
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743218020

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
