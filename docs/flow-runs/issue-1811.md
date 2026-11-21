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
