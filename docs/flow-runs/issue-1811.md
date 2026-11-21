# Flow run record - issue #1811

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=15008b78315749218f268bf83d96d4c1 -->
## Run 1

- Run-id:            15008b78315749218f268bf83d96d4c1
- Run-start:         e32c06edfb52175e4a0678fe51a9a6aea56f671d
- Issue:             #1811
- Base SHA:          e32c06edfb52175e4a0678fe51a9a6aea56f671d
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          run136:cp-orch, mailbox 36336
- Recorded at:       2026-11-21T14:54:46Z

### Section B evidence
#1809 / PR #1815 supplied approval/compliance; #1849 supplied composite finish and parity expansion. #1811 still exempts drift/head-check for all three drivers.

### Section C - the approved plan
1. `templates/delegated-driver-core.md` - add one finish call after push/PR; retain early compliance; offset words through audited acceptance-prose compression, preserving explicit partial-delivery nonclosure.
2. `.claude/commands/codex/auto.md` - render shared core.
3. `.claude/commands/qwen/auto.md` - render shared core.
4. `.claude/commands/gemma/auto.md` - render shared core.
5. `docs/agents/driver-parity.json` - six drift/head-check entries become run.
6. `tests/test_delegated_plan_finish.py` - actual-render ordering/verdict regressions and committed controls.
7. `tests/fixtures/delegated-plan-finish/missing-finish.md` - known-bad Step 7 render.
8. `tests/fixtures/delegated-plan-finish/finish-before-pr.md` - known-bad Step 7 render ordering.
9. `tests/fixtures/delegated-plan-finish/good-finish.md` - known-good Step 7 render.
Scope: drift/head-check rows only; Refs #1811; no budget cap changes, helper behavior changes, merge, or unrelated lane-review cleanup.
Risks: duplicate compliance is deliberate; static tests prove documented placement, not live model execution; compressed prose must preserve each instruction.

### Lanes for this change
| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | not applicable | No checkout-resolution behavior changes. |
| Harness | will test | Claude install command sources and rendered text directly; existing Codex install flow-auto mirror parity; delegated families are not packaged. |
| Driver | will test | `/flow:auto` (Claude implements) / delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`): real renders and flow-derived verb parity. No live delegated run claim. |
| Coordination | not applicable | No with/without Kyle behavior changes. |
| CI provider | not applicable | No provider logic changes; exact-head own CI is separate evidence. |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not: record present, absent and unverified documented dispositions; existing helper wrapper/run tests cover semantics. |
| Toolchain version | not covered | Host and pinned CI only; no version matrix. |
| Clone shape | not applicable | No ref-resolution changes. |
| Run location | not applicable | No path-resolution changes. |
| Gate target | not applicable | No runner/toolchain behavior changes. |
| Wave role state | not applicable | No role lifecycle changes. |

### Changed output readers
Parent orchestrators read all three generated command documents; tests inspect actual renders and known-bad/good Step 7 excerpts. Parity reads command output, six policy rows and the helper composite table. Owner/reviewer read PR and evidence. Static checks do not establish live execution.

<!-- flow-run n=2 id=bee480efb058429fb5ae2a452abdbbfe -->
## Run 2

- Run-id:            bee480efb058429fb5ae2a452abdbbfe
- Run-start:         25f5066ace01373faf0a63b4913a66d26b8becf9
- Issue:             #1811
- Base SHA:          25f5066ace01373faf0a63b4913a66d26b8becf9
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          run136:cp-orch, mailbox 36434
- Recorded at:       2026-11-21T15:32:19Z

### Section B evidence
PR #1869 / squash 25f5066a adopted drift and head-check. Three friction-log.sh parity exemptions remain. This row follows the approved read-only inventory.

### Section C - the approved plan
1. `templates/delegated-driver-core.md` - 49-word parent capture pointer and command before Step 1; offset only Step 1 history. Preserve unresolved-ref-not-zero meaning per approval amendment. Steps 3/5/merge/close unchanged.
2. `.claude/commands/codex/auto.md` - regenerate shared core.
3. `.claude/commands/qwen/auto.md` - regenerate shared core.
4. `.claude/commands/gemma/auto.md` - regenerate shared core.
5. `docs/agents/driver-parity.json` - three friction-log.sh entries become run.
6. `tests/test_delegated_friction_capture.py` - real render/linked policy/active call/negative-control tests.
7. `tests/test_delegated_driver_gates.py` - explicit no-self-approval pin and deletion control.
8. `tests/fixtures/delegated-friction-capture/good.md` - valid pre-Step-1 capture.
9. `tests/fixtures/delegated-friction-capture/missing-call.md` - known-bad missing capture.
10. `tests/fixtures/delegated-friction-capture/commented-call.md` - known-bad inactive command.
11. `tests/fixtures/delegated-friction-capture/after-step-1.md` - known-bad late capture policy.
Scope: friction row only; Refs #1811. No helper behavior changes, word-cap raises, approval-gate trim, unrelated nit fixes, or merge.
Risks: linked policy must remain reachable; static checks prove documented procedure, not runtime capture completeness; Step 1 trim must preserve all operational instructions.

### Lanes for this change
| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | main checkout / linked worktree: existing friction helper tests prove default main-buffer destination in both layouts. |
| Harness | will test | Claude install / Codex install: real command renders plus existing generated flow-auto mirror parity; delegated families remain unpackaged. |
| Driver | will test | `/flow:auto` (Claude implements) / delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`): real command/linked policy checks, no live model run claim. |
| Coordination | not applicable | No with/without Kyle logic change. |
| CI provider | not applicable | No provider behavior change; own exact-head CI recorded separately. |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not: existing friction tests append existing buffer and create absent buffer/parent. |
| Toolchain version | not covered | Host and pinned CI only; no version matrix. |
| Clone shape | not applicable | No history/ref-resolution code changed. |
| Run location | will test | invoked from the CPP root / from another directory: existing friction tests cover repo root, subdirectory and outside git. |
| Gate target | not applicable | No interpreter/PATH boundary change. |
| Wave role state | not applicable | No role-state changes. |

### Changed output readers
Parent orchestrators read generated command documents; new tests feed all actual renders and follow the actual relative link to the flow friction policy. Parity reads commands/policy/composite table. Existing helper tests inspect actual JSONL. Committed bad/good excerpts test the procedure predicate; they do not attest live capture completeness.

<!-- flow-run n=3 id=239ea5cdda114e6d9e1ec9bbb4267b3f -->
## Run 3

- Run-id:            239ea5cdda114e6d9e1ec9bbb4267b3f
- Run-start:         cd6d2b4857165be213b35aa7eac9a0cac4cffffd
### Section A - What this row changes
Delegated planning does not check a generated issue's recorded spec context. A failed issue fetch can look like an ordinary issue if an empty body is checked. Add the parent's context check before planning, after a successful unique-file fetch; unavailable checking is explicitly unchecked, and source context is read before the prompt under the canonical state policy.

### Section B - Still needed
Verdict: Still needed. Main at read time: cd6d2b4857165be213b35aa7eac9a0cac4cffffd.
Read the full issue and owner cap ruling 7065030917. The three speckit-context parity entries remain exempt and the shared Step 2 has no call. Approval: orchestrator mailbox 36690, replying to plan 36689, 2026-11-21. Refs #1811 only; other rows remain. Merge freeze until #1870 lands is retained.

### Section C - Approved changes
1. templates/delegated-driver-core.md - add the parent Step 2 guarded unique-body fetch, real checker call, unavailable-checker unchecked output and canonical source-read-before-prompt policy.
2. .claude/commands/codex/auto.md - generated only; +99 words, 8669 -> 8768.
3. .claude/commands/qwen/auto.md - generated only; +99 words, 9883 -> 9982.
4. .claude/commands/gemma/auto.md - generated only; +99 words, 10492 -> 10591.
5. docs/agents/driver-parity.json - three speckit entries exempt -> run, citation line hints refreshed from unchanged actual text.
6. .claude/command-word-budgets.tsv - caps 8689 -> 8768 (+79), 9905 -> 9982 (+77), 10514 -> 10591 (+77); existing headroom absorbs the rest. Reason: executable gate step, with owner ruling link. No unrelated prose growth.
7. tests/test_delegated_speckit_context.py - real rendered-block execution and documented-procedure controls, no live model-compliance claim.
8. tests/fixtures/delegated-speckit-context/ - committed good and bad procedure cases: unchecked fetch, fixed filename, commented/missing call, missing/late source-read instruction.
9. tests/test_driver_parity.py - real speckit run policy and missing-call discrimination.
10. docs/flow-runs/issue-1811.md - append this approved run, preserve prior history.
11. docs/flow-runs/issue-1811.as-read.md - helper-managed snapshot.
12. docs/flow-runs/issue-1811.lanes-demonstrated.md - append this run's evidence.
13. docs/measurements/counter-model/ - generated runtime-derived different-model review receipt.
Scope: one shared orchestration source, three generated outputs, metadata/tests/evidence. No checker implementation or state-vocabulary change. Risks: failed fetch mistaken for absent, missing checker mistaken for absent, source reading ordered after planning; real execution controls and explicit procedure assertions cover these. No material concern beyond those bounds.

Run each actual-driver regression red on pre-fix cd6d2b48 before the product change. Execute the actual active Step 2 bash with fixture gh and real checker/body generated by its renderer. Cover failed empty/partial fetch, ordinary absent, real generated context, changed state/exit 3, unique files, allocation failure and missing checker. Document source-read-before-plan is a procedure assertion, not live parent compliance. Existing helper tests own state semantics. Commit good/bad controls and exercise actual parity failure when a required speckit call is removed.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | will test - main checkout / linked worktree, fixture-owned roots |
| Harness | will test - Claude install stable-path fixture with real checker; delegated families have no Codex install skills |
| Driver | will test - delegated drivers (/codex:auto, /qwen:auto, /gemma:auto), canonical /flow:auto reference unchanged |
| Coordination | not applicable - no Kyle/no-Kyle behavior change |
| CI provider | not applicable - no status/provider reader change |
| Project state | will test - a repository that has adopted a feature's file or record / one that has not: source-bearing and ordinary bodies, checker unavailable |
| Toolchain version | not applicable - no version-policy change, installed runtime only |
| Clone shape | not applicable - no history-dependent implementation |
| Run location | will test - invoked from the CPP root / from another directory: real checker installed outside fixture target cwd, with root argument resolving the verified target |
| Gate target | not applicable - no finish-gate interpreter policy changes; context runs in the parent |
| Wave role state | not applicable - no role lifecycle change |
| Reader: speckit checker | tested against real output - actual rendered-body file from real renderer via fixture gh, checked by real helper |
| Reader: parent planning session | not covered - live semantic source reading; actual generated text requires source reading before prompt, with canonical state reference checked |
| Reader: parity and procedure tests | tested against real output - actual generated commands, real helper results and actual run-policy entries |

Reader search positively found flow:auto's real speckit call/state reference and the three exemption entries, plus existing helper state tests. gh is a fixture network boundary, not a live GitHub assertion.

Approval: granted in mailbox 36690, including exact cap raises under owner ruling 7065030917. Before push run budget, both import-audit paths, full own finish gate, pinned head-history gitleaks and exact-head CI. Use normal account HOME, private TMPDIR outside it, no inherited basetemp/PYTEST_ADDOPTS, reset SIGINT and warm private cache. Review identities derive from runtime logs. After #1870 lands merge main/recheck/re-gate before orchestrator merge; no force push or rendered hand edits.

<!-- flow-run n=4 id=f035e5fd6e3149d7936f5326621f165a -->
## Run 4

- Run-id:            f035e5fd6e3149d7936f5326621f165a
- Run-start:         787498475c5655792053cd4bd056367617e00e46

- Issue:             #1811
- Base SHA:          787498475c5655792053cd4bd056367617e00e46
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          run136:cp-orch, mailbox 36784 (reaffirmed 36887)
- Recorded at:       2026-11-21T18:59:37.820587+00:00

### Section B evidence
PR #1879 / squash 78749847 supplied the speckit row and Run 3. The live-driver, claim and stale rows remain exempt for all three drivers. Plan 36782 approved in 36784, with required mixed own/foreign dirt control; begin after speckit push/current-main integration as confirmed in 36887.

### Section C - the approved plan
1. `templates/delegated-driver-core.md` - parent checks after approval/before first child, stale check Step 6 start, live guard before fixes, ownership-aware checkpoint/recheck and own-only cleanup release.
2. `.claude/commands/codex/auto.md` - regenerate shared core.
3. `.claude/commands/qwen/auto.md` - regenerate shared core.
4. `.claude/commands/gemma/auto.md` - regenerate shared core.
5. `docs/agents/driver-parity.json` - nine helper/driver entries exempt to run; refresh actual citation hints.
6. `.claude/command-word-budgets.tsv` - exact measured caps, executable gate step and owner ruling; retain sibling gates.
7. `tests/test_delegated_pre_child_guards.py` - actual-render ordering/verdict and real helper execution; mixed own/foreign dirt never swept into checkpoint.
8. `tests/fixtures/delegated-pre-child-guards/` - committed good/bad ordering, verdict, ownership, cleanup and review-renewal controls.
9. `tests/test_driver_parity.py` - actual nine-entry policy and missing-call discrimination.
Scope: three pre-child helper rows only; Refs #1811; helper implementations unchanged. No bypass of live suspected, claim held/foreign, review renewal or approval gates. Exact cap increases allowed as executable gate steps.
Risks: live freshness cannot distinguish own/foreign dirt; only confirmed own edits may be checkpointed, then guard reruns clean. Unknown dirt or persistent suspected STOP/ask. No live model compliance claim.

### Lanes for this change
| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | Real fixture-owned main checkout and linked worktree helper calls. |
| Harness | will test | Claude install stable helper path fixture and generated documents; Codex install delegated drivers are intentionally not packaged (not applicable). |
| Driver | will test | /flow:auto (Claude implements) unchanged; delegated drivers (/codex:auto, /qwen:auto, /gemma:auto) actual renders and real parity policy. |
| Coordination | not applicable | No Kyle/no-Kyle authority behavior change. |
| CI provider | not applicable | No status/provider logic change. |
| Project state | will test | A repository that has adopted a feature's file or record / one that has not: clean/own-dirty/mixed foreign dirt; self/held claims; current/collision/unknown stale state. |
| Toolchain version | not covered | Installed runtime and pinned CI only; no matrix. |
| Clone shape | not applicable | No new clone/ref-resolution behavior. |
| Run location | will test | Invoked from the CPP root / from another directory: literal target path while helper caller is elsewhere. |
| Gate target | not applicable | Parent helper checks do not alter runner interpreter selection. |
| Wave role state | not applicable | No wave lifecycle change. |
| Reader: parent session | not covered | Live model compliance; documented ordering/verdict policy is tested against actual rendered text and committed bad cases. |
| Reader: rendered command tests | tested against real output | Execute actual extracted Bash calls against real helpers in fixture-owned repositories. |
| Reader: parity checker | tested against real output | Nine real run-policy entries and one missing-call control per driver/helper. |

Reader search: grep positively found canonical flow:auto calls to all three helpers and the nine delegated policy exemptions; existing real helper tests consume their emitted path/verdict lines. No helper output shape changes.

Approved policy in full:
# CPP #1811 queued pre-child trio: read-only plan

Start only after the current speckit PR reaches its handoff; create a separate branch/worktree from then-current origin/main. Refs #1811; do not close the umbrella. No source changes yet.

Outcome: parent runs live-driver, claim and stale checks after Step 3 approval and immediately before Step 4 first child invocation, and repeats the required checks before Step 6 fixes. Release only this run's claim immediately before Step 8 removal.

Placement and verdicts
- Shared TEMPLATE at end of Step 3, before vendor Step 4; literal recorded WT_PATH arguments, validate helper output names that checkout. Missing/unknown helpers are reported as unchecked, never clear. Live-driver clear proceeds; suspected STOP/ask, not an automatic authorization. Claim explicit check: self healthy; held/foreign STOP, report ownership; unresolved ownership never starts child. If free/stale, use existing normal acquisition semantics and recheck, never --steal.
- Stale check origin/main + literal WT_PATH before Step 4 and at Step 6 start. Current/moved-clean without overlap proceeds. Collision or an intended file changed upstream: checkpoint only positively attributed own work, merge on a clean tree, no shared stash. Missing/fetch failure remains advisory/unchecked and is reported.
- Before each Step 6 child fix, rerun live-driver guard; recheck claim if ownership uncertain. Own-dirty policy proposal: known recent edits alone do not prove foreign activity, but suspected cannot be bypassed. Attribute any dirty content against this run's recorded checkpoint/child result, checkpoint only confirmed own changes, and rerun the guard on the clean tree. Unexplained changes or a persisting suspected verdict STOP/ask. Never commit uncertain foreign edits. Any changed reviewed artifact returns to Step 5 independent review/receipt before finish. This makes no helper-contract changes.
- Cleanup: release literal WT_PATH only after merge/own-claim confirmation and immediately before removal; never --force or release a foreign claim. Leave-for-review retains the worktree and claim.

Surfaces
- templates/delegated-driver-core.md; generated codex/qwen/gemma auto.md via make delegated-core-write.
- Exactly nine parity exemptions become run (three helpers x three drivers); refresh citation line hints using actual cited text.
- tests/test_delegated_pre_child_guards.py plus committed good/bad driver fixtures; extend actual policy-driven parity controls. Existing helper product behavior unchanged; existing helper tests establish real verdict contracts.
- .claude/command-word-budgets.tsv exact measured counts after current-main integration, retain all sibling gates, owner-authorized executable gate step rationale with #1811 ruling.
- Approved plan/run evidence and derived counter-model receipt.

Validation
Run new actual-driver regressions on pre-fix current-main and require red before edits. Extract active Bash calls and assert initial/fix ordering, literal paths, path/verdict mapping, suspected STOP, own-work checkpoint-and-recheck rather than bypass, claim held stop, release before deletion and no leave-for-review release, stale merge checkpoint and changed-artifact review renewal. Committed negative controls remove/move each call and invert verdict/ownership/cleanup behavior. Pair fixture verdicts with existing real helper tests; claim no live model compliance proof. Run focused helper + rendered contract/parity suites, vendor check, exact-cap checker plus one-word-over controls for all drivers, lint/typecheck/import audits, independent review and full exact-head finish gate.

Approved by orchestrator mailbox verdict 36784 on 2026-11-21. Start from current main after the speckit PR is pushed. Additional required committed case: foreign dirt beside confirmed-own dirt in the same tree must STOP; the checkpoint must not sweep the foreign change in. The own-dirty policy is explicitly approved; no bypass of suspected is authorized.

<!-- flow-run n=5 id=03776eb0b3d5448a9ab2d99b0e00cb74 -->
## Run 5

- Run-id:            03776eb0b3d5448a9ab2d99b0e00cb74
- Run-start:         dbb485d4d1d7e9dc55e227822896c24f5b467712
- Issue: #1811
- Necessity verdict: Still needed
- Approval: granted
- Approver: run136:cp-orch mailbox 36767; cap-conflict rule 36773

### Section B evidence
The delegated shared lifecycle has a checkpoint commit before either post-child safety guard. The owner requires all #1811 rows adopted before release. This run adopts only the two post-child rows; prior runs and other workers own the others.

### Section C - the approved plan
1. `templates/delegated-driver-core.md` - parent strict worktree guard after Step 4 return, every Step 6 fix return, and before any Step 7 shipping commit; ignored-additions before first Step 5 checkpoint and Step 7 shipping commit. Guard leak exit 3 STOP, unknown/not-applicable 4/5 report exactly; attribute main edits before reverting. Ignored-additions exit 3 STOP.
2. `.claude/commands/codex/auto.md`, `.claude/commands/qwen/auto.md`, `.claude/commands/gemma/auto.md` - regenerate from template, never hand-edit rendered regions.
3. `docs/agents/driver-parity.json` - six adopted entries become run.
4. `tests/test_delegated_post_child_guards.py` - actual rendered placement and verdict contract regression; committed good, missing-call and after-first-commit inputs reject broken placement. Red on unchanged main first.
5. `tests/fixtures/delegated-post-child/` - committed bounded known-good and known-bad driver excerpts.
6. `.claude/command-word-budgets.tsv` - raise only exceeded caps to exact measured count, owner ruling (f), executable gate step. On main conflicts preserve template changes, regenerate and recount, never choose either rendered side.
Evidence: existing helper verdict tests/controls, targeted render/parity tests, command budgets, independent reviewer and CPP full gate; exact-head CI. Refs #1811, no closing reference. No helper implementation changes or unrelated rows.

### Lanes for this change
| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | main checkout / linked worktree: existing worktree guard and ignored-additions cases exercise each layout and third-state verdicts. |
| Harness | will test | Claude install / Codex install: vendor/parity validates real Claude renders and generated Codex flow-auto mirror; delegated drivers intentionally unpackaged. |
| Driver | will test | /flow:auto / delegated drivers: actual three delegated renders gain calls and parity membership against flow. |
| Coordination | not applicable | Parent documentation only; no Kyle authority behavior. |
| CI provider | not applicable | No provider logic changed; own Woodpecker CI separately required. |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not: existing ignored-addition tests distinguish suspicious ignored files and clean runs. |
| Toolchain version | not covered | Host/pinned CI only; no version matrix. |
| Clone shape | not applicable | No history/ref-resolution behavior changed. |
| Run location | not applicable | Guard calls execute from target worktree as already required by lifecycle. |
| Gate target | not applicable | No runner interpreter/PATH change. |
| Wave role state | not applicable | No wave role changes. |

### Changed output readers
Parents read generated command documents. Rendered placement tests consume all three actual command files and committed bounded excerpts; parity consumes actual renders and policy. Existing tests/controls consume actual helper verdicts. No live delegated-run completeness claim.

<!-- flow-run n=6 id=886f56f62f81479da3e05c5b76a2b489 -->
## Run 6

- Run-id:            886f56f62f81479da3e05c5b76a2b489
- Run-start:         6dec8d527be32788cdb6754909f1aaa0210563e2

- Issue:             #1811
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          run136:cp-orch, mailbox 37110

### Section B evidence
Three nit-store-resolve.sh parity entries still declare a known gap. The shared core lacks parent retention and close-time routing. Other rows remain out of scope. Read current issue and owner cap ruling 7065030917. Approval 37110 accepts the plan in mailbox 37107, normal-HOME gate setup, and current-main-first sequencing.

### Section C - the approved plan
1. `templates/delegated-driver-core.md` - parent Step 5 retains supplemental/deferred findings and context; parent Step 7 routes after PR/plan finish, before report/cleanup. Bare installed resolver, explicit returned repository, ok/none/unknown, no child writes, standalone records, closing links, serious defects own issues, ordinary zero outcome; link flow:auto Step 5b.
2. `.claude/commands/codex/auto.md` - regenerate shared core.
3. `.claude/commands/qwen/auto.md` - regenerate shared core.
4. `.claude/commands/gemma/auto.md` - regenerate shared core.
5. `docs/agents/driver-parity.json` - exactly three nit-store exemptions become run.
6. `.claude/command-word-budgets.tsv` - exact recounted three auto caps under ruling (f); executable gate step. Baseline preview added 198 words per driver, consuming headroom first; remeasure after current-main integration.
7. `tests/test_delegated_nit_store_routing.py` - actual-render parent scope/order, semantic policy, controls, actual published resolver execution with fake GitHub and restricted PATH.
8. `controls/delegated-nit-store-routing/cases.json` - committed good/bad procedure mutation inputs, exercised by the test suite; no standalone gate added.

Scope: nit-store row only, Refs #1811. No resolver change, child GitHub writes, slot edits, flow:auto change, or other gate-row changes. First execute regressions red on current main, then green after implementation. Explicit negative cases: missing --repo, unknown treated as none, missing closing link/context, absent bare call, child-scope retention/routing. Actual helper states: mapped/searched ok, none, unknown transport/ambiguity, missing helper, renamed callers, main/linked checkout. Fake GitHub never writes externally. No bare Python in new published shell; test stub uses sys.executable.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | will test - main checkout / linked worktree, fixture-owned repositories and actual published block |
| Harness | will test - Claude install-shaped ~/.claude/scripts symlink; delegated families have no Codex install skill; live model obedience not covered |
| Driver | will test - delegated drivers (/codex:auto, /qwen:auto, /gemma:auto), actual renders; canonical /flow:auto unchanged and existing routing tests re-run |
| Coordination | not applicable - no Kyle-specific routing branch; live fleet not covered |
| CI provider | not applicable - no provider-specific behavior; exact-head CPP Woodpecker required separately, live Actions not covered |
| Project state | will test - a repository that has adopted a feature's file or record / one that has not: installed helper present/missing and open/absent store |
| Toolchain version | will test - the host or container's installed versions and restricted PATH; CI's pinned uv and Python via CI, no version matrix claim |
| Clone shape | not applicable - no history-dependent resolver behavior; full and fixture clones only |
| Run location | will test - invoked from the CPP root / from another directory, installed resolver outside owned target, renamed worktree caller |
| Gate target | will test - CPP itself / a consumer with its own interpreter and PATH: owned consumer target and no-bare-Python PATH; no consumer Python used by block |
| Wave role state | not applicable - no registry lifecycle change |
| Reader: generated-command parent | not covered - live semantic obedience; actual generated output tested structurally with omission controls |
| Reader: parity checker | tested against real output - actual regenerated driver documents and ledger |
| Reader: resolver output consumer | tested against real output - actual helper invoked through published block; live model branching not covered, helper format unchanged |
| Reader: GitHub and closing report | not covered - live writes/report generation; presence controls require explicit repository, complete record, refusal on unknown and closing links |

Reader search: git grep for delegated-core-vendor, nit-store-resolve.sh and driver-parity.json positively found scripts/check-driver-parity.py and the actual vendor/routing tests. External reader exhaustiveness not claimed. No helper output format changes.

Verification: related resolver/routing/vendor/parity tests and controls; budget check, bandit and undeclared-import audits including selftests; gitleaks --log-opts=HEAD; own-checkout full finish gate with self-notify and kyle-lock, normal HOME, private sibling TMPDIR and no inherited ADDOPTS/basetemp. Warm current-lock uv cache if necessary. Independent counter-model review with runtime-derived different model and honest receipt; instruction preservation review. Merge sibling template changes, regenerate/recount exact caps at final merge. Begin-run after main integration; if run-number collision remains, mailbox 37078 allows one header/marker-only administrative re-approve of unchanged approved body at final merge, preserving upstream sections verbatim. No declare-salvage work until this PR pushed.
