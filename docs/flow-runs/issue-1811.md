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
