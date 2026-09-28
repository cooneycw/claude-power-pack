# Issue #1268 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1268
- Read at:      2026-09-28T16:20:25Z
- updatedAt:    2026-09-26T14:12:43Z   (context only - moves on comments and labels)
- Body digest:  80d5982d3bf62b6038fc816a4d3070f969327937ef05aca768c3a724fb48bb9c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 13401 of 13401 (cap 16384)

## Body as read
**Wave W3D**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S3**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S3** A numbered markdown row anywhere in ADR 0008 (any table) is read as a census row (live; related #1036; found during #1060 counter-model review (Codex finding))
  - evidence: scripts/check-negative-controls.py:562 ADR_ROW_RE and scripts/instrument-census-check.py:158 CENSUS_ROW_RE both still match `^\|\s*\d+\s*\|` over the whole (fence/comment-stripped) doc, not scoped to the census table by header; latent (one numbered table, 106 rows today)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741489733
- [ ] **S3** instrument-census-check.py never verifies census row numbers are unique; concurrent PRs can duplicate a row (live; found during #1068 / PR #1090)
  - evidence: scripts/instrument-census-check.py:158 CENSUS_ROW_RE matches then discards the number; no duplicate-detection code found anywhere in scripts/; current ADR: 106 distinct rows, no dup today, gaps at 32/45
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743583840
- [ ] **S3** ADR 0008's hand-typed sequential row number is a collision magnet and goes stale wherever cited in prose (live; related #1002, #1036; found during #1068 / PR #1090)
  - evidence: same unaddressed CENSUS_ROW_RE/no-uniqueness-check as idx=173; no keying-on-instrument-path alternative implemented
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743992802
- [ ] **S3** ADR 0008 census has no RETIRED state; retiring one instrument costs four artifacts (live; found during #1069 (PR #1144), retiring project-next-vendor.py --upstream (row 32))
  - evidence: docs/decisions/0008-instrument-negative-control-bound.md:283 (gap comment), :282/:284 (row-32 numbering gap), :597 (prose paragraph) - still four separate artifacts, no first-class RETIRED row state
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751057427
- [ ] **S3** ADR 0008 census row 101 names the wrong CI consumer step (live; related 1132; found during #1146, appending census row 102)
  - evidence: docs/decisions/0008-instrument-negative-control-bound.md row 101 consumer column still reads '... CI claude-md-behavior-check sibling step' instead of cpp-host-writes-check
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751620985
- [ ] **S3** ADR 0008 row 103 REFUSED wording is narrower than the gate's actual refusal causes (live; found during PR #1213 / issue #1182)
  - evidence: docs/decisions/0008-instrument-negative-control-bound.md:353 still says `REFUSED - <sandbox problem>`, not naming the git-containment refusal cause added by #1182
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5795185057
- [ ] **S3** check-negative-controls.py reports census non-members but never fails on them (open decision) (live; related 1036; found during #1036 / PR #1124)
  - evidence: scripts/check-negative-controls.py:2135-2148 census_membership prints NEGATIVE_CONTROL_CENSUS_NONMEMBER but exit code unaffected
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749939915
- [ ] **S3** check-negative-controls.py hardcodes CPP's own ADR path; blind in every consumer repo (live; found during owner-requested negative-control regime audit (no issue))
  - evidence: scripts/check-negative-controls.py:561 `ADR_0008 = Path("docs/decisions/0008-instrument-negative-control-bound.md")`, no --census override
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741239578
- [ ] **S3** eli5-check and tool-risk-check hard gates excluded from make verify with a non-reason (live; related 1028; found during #1028)
  - evidence: Makefile:860,895 still print identical reason text "nothing about it needs the network or this host"; not wired into verify
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749670470
- [ ] **S3** check-control-ci-deps.py scopes to the one CI step that runs check-negative-controls.py, missing a second battery-driving step (live; related 1036; found during #970 / PR #1128)
  - evidence: scripts/check-control-ci-deps.py:149-152 BATTERY_GATE_REL/BATTERY_SCRIPT still hardcode check-negative-controls.py only; mutation-probe.py step not enumerated
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750142301
- [ ] **S3** docs/research sweep.py's RED bucket control is falsified on main and nothing runs the sweep (live; related 970; found during #970 / PR #1128)
  - evidence: docs/research/class-enumeration-2026-09-15/sweep.py:396 RED bucket check still present; not referenced in Makefile or .woodpecker.yml
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750142796
- [ ] **S3** Forced-claim prototype has 3 uncontrolled protections and its selftest conflates no-runner with failed battery (live; related 1128; found during #970 / PR #1128)
  - evidence: research prototype outside controls/ and outside CI, per author's own scope note; not independently re-run here
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750143330
- [ ] **S3** controls/gate-lib declares no mutations, the newest control with none (live; related 970; found during #1126)
  - evidence: controls/gate-lib/control.json has no mutations key per author; register verdict already PASS with anchor blind, so a strengthening not a gap
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750282841
- [ ] **S3** mutation-probe applies mutations one at a time, so mutually-masking protections both read UNCAUGHT (live; related 1129; found during #1129 / PR #1135)
  - evidence: scripts/mutation-probe.py single-mutation design per author; shellcheck-gate's zero-matched-is-unknown / linter-crash-is-unknown pair cited as example, not a false green (both expect:uncaught with reasons)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750456574
- [ ] **S3** control.json prose-key spelling is inconsistent (_comment vs limits) (live; found during #1157)
  - evidence: Measured on main: 34 controls/*/control.json files use a top-level "limits" key, 23 use "_comment", 6 use both - the inconsistency is worse now than the nit's own '1 vs ~34' count, and neither key is read programmatically
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5763502991
- [ ] **S3** check-negative-controls.py anchor diagnostics label constructed anchors 'n/a' with no case identity (live; found during building control for #1084 half A)
  - evidence: scripts/check-negative-controls.py:1795 (and 1738/1750/1759/1774/1782/1791) still interpolate anchor['sha'] rather than anchor['path'], and per-case lines carry no case name
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5767678011
- [ ] **S3** Regenerating a blind anchor from its gate silently drops a load-bearing path adaptation (live; found during PR #1213 / issue #1182)
  - evidence: controls/host-surface-observe/anchors/constructed-blind-covered-by.py docstring (~L13-23) documents the REPO_ROOT parents[3] adaptation manually; no scripts/regenerate-blind-anchor.sh or make target exists to encode it
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5795181614
- [ ] **S3** ROUTED_SURFACES is a hardcoded tuple, cannot see a new unrouted authoring surface (live; related 834; found during 834)
  - evidence: tests/test_issue_contract_routing.py:47-56 ROUTED_SURFACES still a fixed tuple; docstring at :19-23 still names the gap
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5648583791
- [ ] **S3** control.json anchors[].kind field only partially read; historical-vs-constructed distinction still inert (partially-delivered; related 924; found during 959)
  - evidence: scripts/check-negative-controls.py:2000 now reads `anchor.get("kind") == "synthetic"` (new since filing) but the historical/constructed distinction the nit is about is still not validated or reported
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5677799228
- [ ] **S3** .gitignore negation list is a hand-maintained enumeration that got lucky again (live; related 1012; found during #962 / PR #1118)
  - evidence: .gitignore:125 !controls/*/cases/**/*.json still the only protection; not a live hole (fail-loud detector exists)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749662078
- [ ] **S3** Finish-gate re-run re-executes the whole test step even when the failure is phase-2-only (live; related 769; found during kyle#1149+#1146)
  - evidence: lib/cicd/runner.py:1238 `rerun_result = step.execute(rerun_context)` still re-runs the whole step
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5654148088
- [ ] **S3** ruff has no positive-coverage signal, so `lint` coverage is reported unknown by design (live; found during #1027)
  - evidence: lib/cicd/coverage.py:138-188 documents ruff's silent "All checks passed!" whenever pyproject.toml exists; lint stage deliberately reports UNKNOWN rather than a fabricated zero
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741868372
- [ ] **S3** Security scan counts the CI runner's own .claude/cicd-state JSON as a scanned source file (live; found during #1027)
  - evidence: lib/security/modules/secrets.py:96-107: `.json` in SCAN_EXTENSIONS, `.claude` absent from SKIP_DIRS
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741869053
- [ ] **S3** pip_audit.py relies on an -O-erasable assert to reject an unreachable-by-convention return shape (live; related 1114; found during #1114 / PR #1123)
  - evidence: lib/security/modules/pip_audit.py assert temporary_requirement is not None still the only guard; bound recorded in docs/decisions/0010
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749931003
- [ ] **S3** conftest.py's _guarded_binaries() anchors on __file__ instead of the imported package, breaking inside a pytester sub-run (live; found during issue #1232 / PR #1238)
  - evidence: tests/conftest.py:282 `_guarded_binaries()` still uses `Path(__file__).resolve().parents[1]`, not the module-level `REPO_ROOT = Path(_tests_package.__file__).resolve().parents[1]` added at line 21 for exactly this purpose (added by #1232)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5812196733
- [ ] **S3** toolchain-provenance.sh dates the fetched remote ref, not the stale local HEAD, in a 'behind' verdict (live; related 1029; found during wave claude-improvements, worker-A)
  - evidence: scripts/toolchain-provenance.sh:296-301 age_clause() still only reports FETCH_AGE (upstream ref); the 'behind' line (:311) never states HEAD's own age
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5775240665
- [ ] **S3** A clone-stage CI infra failure is indistinguishable from a real code failure; flow-ci-status.sh has no precode-failure marker (live; related 1022; found during PR #1040 / #1022)
  - evidence: scripts/flow-ci-status.sh still only emits FLOW_CI_FAILED_STEP (:126); no FLOW_CI_PRECODE_FAILURE or equivalent marker exists
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5705043985
- [ ] **S3** An edited GitHub issue comment is indistinguishable from an original in every gh reading path (live; found during wave cpp-completion)
  - evidence: No script in scripts/ compares updated_at to created_at for issue comments (grep for that pattern finds nothing relevant); no (edited) marker surfaced anywhere
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5678304161
- [ ] **S3** Presence-only /proc occupancy scans: a zero means 'not now', never 'not ever' - a reasoning hazard, not a code defect (live; related #1032; found during orchestrating post-#1031 CPP sessions)
  - evidence: no code fix owed/proposed; scripts/worktree-remove.sh confirmed to already emit clear|unknown|occupied-clean|occupied-dirty (unknown != clean), which the entry itself verifies
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743625725
- [ ] **S3** Refresh #1150's observation population before implementing its harness (unverified; related 1150; found during #1150 acceptance work)
  - evidence: scripts/host-surface-check.py currently reports 'all 16 reachable script(s)' matching the nit's own refreshed count; whether #1150's future harness implementation used stale 9/6 counts could not be cheaply confirmed
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5763859905

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
